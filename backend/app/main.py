from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit import audit_event
from .auth import require_access, token_matches
from .config import get_settings
from .database import AnalysisJob, cleanup_expired_rows, get_db, init_db, new_expiry
from .fetcher import fetch_public_image
from .metrics import increment, render_prometheus
from .queueing import enqueue_analysis
from .rate_limit import client_key, enforce_rate_limit
from .reports import build_pdf_report
from .storage import EncryptedBlobStore

settings = get_settings()
store = EncryptedBlobStore(settings)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_FALLBACK = FRONTEND_DIST / "fallback.js"


@asynccontextmanager
async def lifespan(_: FastAPI):
    production_errors = settings.production_errors()
    if production_errors:
        raise RuntimeError("Invalid production configuration: " + " ".join(production_errors))
    init_db()
    db = next(get_db())
    try:
        store.cleanup_paths(cleanup_expired_rows(db))
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/analyses"):
        response.headers.setdefault("Cache-Control", "no-store")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    increment("aida_http_requests_total", method=request.method, path=_metric_path(request.url.path), status=response.status_code)
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    checks: dict[str, str] = {}
    status_code = 200
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        status_code = 503

    if settings.use_rq:
        try:
            Redis.from_url(settings.redis_url).ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
            status_code = 503
    else:
        checks["redis"] = "not_required"

    return JSONResponse({"status": "ok" if status_code == 200 else "degraded", "checks": checks}, status_code=status_code)


@app.get("/metrics", include_in_schema=False)
def metrics(request: Request) -> Response:
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics are disabled.")
    token = request.headers.get("x-aida-access-token") or request.cookies.get("aida_access_token")
    if settings.require_access_token and not token_matches(token, settings):
        raise HTTPException(status_code=401, detail="A valid access token is required.")
    return Response(render_prometheus(), media_type="text/plain; version=0.0.4")


@app.head("/", include_in_schema=False)
def frontend_index_head() -> Response:
    if not FRONTEND_INDEX.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build in the frontend directory.")
    return Response(media_type="text/html")


@app.get("/", include_in_schema=False)
def serve_frontend_index() -> FileResponse:
    if not FRONTEND_INDEX.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build in the frontend directory.")
    return FileResponse(FRONTEND_INDEX)


@app.get("/fallback.js", include_in_schema=False)
def serve_frontend_fallback() -> FileResponse:
    if not FRONTEND_FALLBACK.exists():
        raise HTTPException(status_code=404, detail="Frontend fallback not found. Run npm run build in the frontend directory.")
    return FileResponse(FRONTEND_FALLBACK, media_type="text/javascript")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.post("/analyses", status_code=202)
async def create_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(require_access)] = None,
    file: Annotated[UploadFile | None, File()] = None,
    url: Annotated[str | None, Form()] = None,
    consent_confirmed: Annotated[bool, Form()] = False,
) -> dict:
    enforce_rate_limit(request, bucket="analysis_create", limit=settings.analysis_rate_limit_max_requests, settings=settings)
    if not consent_confirmed:
        raise HTTPException(status_code=400, detail="Consent confirmation is required before analyzing sensitive media.")
    if bool(file) == bool(url):
        raise HTTPException(status_code=400, detail="Provide exactly one input: an image upload or a public URL.")

    analysis_id = str(uuid.uuid4())
    source_context: dict = {}
    source_url: str | None = None
    input_kind = "upload"

    if file:
        image_bytes = await _read_upload(file)
        source_context = {
            "input_filename": file.filename,
            "content_type": file.content_type,
            "attribution_boundary": "Direct upload; no public source attribution was attempted.",
        }
    else:
        input_kind = "url"
        source_url = url
        fetched = await fetch_public_image(url or "", settings)
        image_bytes = fetched.image_bytes
        source_context = fetched.context

    blob_path = store.save(analysis_id, image_bytes)
    job = AnalysisJob(
        id=analysis_id,
        status="pending",
        input_kind=input_kind,
        source_url=source_url,
        blob_path=str(blob_path),
        source_context=source_context,
        expires_at=new_expiry(),
    )
    db.add(job)
    db.commit()

    queue = enqueue_analysis(analysis_id, background_tasks)
    increment("aida_analysis_created_total", input_kind=input_kind, queue=queue)
    audit_event(
        "analysis.created",
        analysis_id=analysis_id,
        input_kind=input_kind,
        queue=queue,
        client=client_key(request, settings),
        content_type=source_context.get("content_type"),
        domain=source_context.get("domain"),
    )
    return {"id": analysis_id, "status": job.status, "queue": queue, "expires_at": job.expires_at.isoformat()}


@app.get("/analyses/{analysis_id}")
def get_analysis(
    request: Request,
    analysis_id: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(require_access)] = None,
) -> dict:
    enforce_rate_limit(request, bucket="analysis_read", limit=settings.rate_limit_max_requests, settings=settings)
    job = db.get(AnalysisJob, analysis_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis was not found or has expired.")
    return _job_payload(job)


@app.get("/analyses/{analysis_id}/report")
def get_report(
    request: Request,
    analysis_id: str,
    db: Annotated[Session, Depends(get_db)],
    format: Annotated[str, Query(pattern="^(json|pdf)$")] = "json",
    _: Annotated[None, Depends(require_access)] = None,
) -> Response:
    enforce_rate_limit(request, bucket="report_read", limit=settings.rate_limit_max_requests, settings=settings)
    job = db.get(AnalysisJob, analysis_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis was not found or has expired.")
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=409, detail="Analysis report is not ready yet.")

    if format == "pdf":
        pdf = build_pdf_report(job.result)
        audit_event("analysis.report_downloaded", analysis_id=analysis_id, format=format, client=client_key(request, settings))
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="analysis-{analysis_id}.pdf"'},
        )
    audit_event("analysis.report_downloaded", analysis_id=analysis_id, format=format, client=client_key(request, settings))
    return JSONResponse(job.result)


@app.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(
    request: Request,
    analysis_id: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(require_access)] = None,
) -> Response:
    enforce_rate_limit(request, bucket="analysis_delete", limit=settings.rate_limit_max_requests, settings=settings)
    job = db.get(AnalysisJob, analysis_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis was not found or has expired.")
    store.delete(job.blob_path)
    db.delete(job)
    db.commit()
    increment("aida_analysis_deleted_total")
    audit_event("analysis.deleted", analysis_id=analysis_id, client=client_key(request, settings))
    return Response(status_code=204)


async def _read_upload(file: UploadFile) -> bytes:
    if file.content_type and file.content_type.split(";")[0].lower() not in settings.allowed_image_types:
        raise HTTPException(status_code=415, detail="Unsupported image type.")
    image_bytes = await file.read(settings.max_upload_bytes + 1)
    if len(image_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image is larger than the configured limit.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")
    return image_bytes


def _job_payload(job: AnalysisJob) -> dict:
    payload = {
        "id": job.id,
        "status": job.status,
        "input_kind": job.input_kind,
        "source_url": job.source_url,
        "source_context": job.source_context,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
    }
    if job.status == "completed":
        payload["result"] = job.result
    return payload


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


def _metric_path(path: str) -> str:
    if path.startswith("/analyses/"):
        if path.endswith("/report"):
            return "/analyses/{id}/report"
        return "/analyses/{id}"
    return path
