from datetime import UTC, datetime

from sqlalchemy.orm import Session

from .analysis import analyze_image_bytes
from .audit import audit_event
from .database import AnalysisJob, SessionLocal
from .metrics import increment
from .storage import EncryptedBlobStore


def process_analysis_job(analysis_id: str) -> None:
    store = EncryptedBlobStore()
    db: Session = SessionLocal()
    job = db.get(AnalysisJob, analysis_id)
    if not job:
        db.close()
        return

    try:
        job.status = "running"
        job.updated_at = datetime.now(UTC)
        db.commit()

        if not job.blob_path:
            raise ValueError("Analysis media is missing.")
        image_bytes = store.read(job.blob_path)
        result = analyze_image_bytes(image_bytes, source_context=job.source_context)

        job.status = "completed"
        job.result = result
        job.error = None
        job.updated_at = datetime.now(UTC)
        store.delete(job.blob_path)
        job.blob_path = None
        db.commit()
        increment("aida_analysis_completed_total", verdict=result["verdict"]["label"])
        audit_event("analysis.completed", analysis_id=analysis_id, verdict=result["verdict"]["label"], confidence=result["verdict"]["confidence"])
    except Exception as exc:
        job.status = "failed"
        job.error = _safe_error(exc)
        job.updated_at = datetime.now(UTC)
        store.delete(job.blob_path)
        job.blob_path = None
        db.commit()
        increment("aida_analysis_failed_total", error=exc.__class__.__name__)
        audit_event("analysis.failed", analysis_id=analysis_id, error=exc.__class__.__name__)
    finally:
        db.close()


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    return message[:300]
