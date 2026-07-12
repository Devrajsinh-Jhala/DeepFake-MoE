---
title: AI Deepfake Analyzer
sdk: docker
app_port: 8000
suggested_hardware: cpu-basic
models:
  - buildborderless/CommunityForensics-DeepfakeDet-ViT
  - Ateeqq/ai-vs-human-image-detector
  - jacoballessio/ai-image-detect-distilled
---

# AI Deepfake Analyzer

Privacy-first public application for layered image authenticity analysis. The app accepts an image upload or a public URL, runs metadata/provenance/forensic checks plus an open-source calibrated model ensemble, and returns a victim-friendly report with a technical appendix.

The first version is intentionally cautious: it reports probabilities and evidence, not certainty. Raw media is encrypted while queued and deleted after analysis.

## Report Quality

Each completed analysis now includes:

- A victim-friendly verdict with confidence, AI evidence score, manipulation evidence, and cross-layer disagreement.
- A mixture-of-experts opinion ledger covering the five-view broad primary, two counter-models, provenance, forensic residuals, input quality, and safety arbiter.
- A decision summary that separates primary drivers, counter-evidence, uncertainty factors, and evidence that would improve confidence.
- An 11-layer ledger covering metadata/provenance, visual consensus, model-transform robustness, luminance, chroma, edge geometry, noise residual, compression/ELA, frequency spectrum, and regional tile anomalies. Every layer states its role, reliability, influence, and counterfactual.
- An abstract 4x4 region evidence map. The map shows relative anomaly severity without rendering the uploaded image in the report.
- A technical appendix with hashes, detector outputs, reproducibility notes, and redacted metadata summaries. Raw XMP/XML metadata is not stored in reports.

## Public Landing Page

The frontend now opens with a public-facing architecture page before the analyzer. It explains:

- The input boundary and sensitive-media privacy posture.
- The evidence-layer pipeline.
- The open-source detector mixture of experts.
- The calibrated safety arbiter and abstention policy.
- Deployment controls needed for public operation.

The analyzer remains on the same page at `#analyzer` so users can move directly from the explanation to upload/public URL analysis.

## Quick Start

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open `http://localhost:5173` for the Vite dev UI. After running `npm run build` in `frontend`, the backend also serves the app at `http://localhost:8000`.

## Configuration

Backend settings use the `AIDA_` prefix.

- `AIDA_DEPLOYMENT_MODE`: use `local` for development and `production` for public deployment validation.
- `AIDA_DATABASE_URL`: SQLAlchemy URL. Defaults to local SQLite at `backend/.data/app.db`; use PostgreSQL in production.
- `AIDA_DATA_DIR`: encrypted blob/report state directory. Defaults to `backend/.data`.
- `AIDA_REDIS_URL`: Redis URL for RQ. Defaults to `redis://localhost:6379/0`.
- `AIDA_USE_RQ`: set `true` to enqueue analyses through Redis/RQ.
- `AIDA_ENCRYPTION_KEY`: Fernet key for encrypted temporary media. If omitted, an in-memory key is generated for the current process.
- `AIDA_ENABLE_HF_MODEL`: set `true` to enable the optional Hugging Face image-classification adapter.
- `AIDA_HF_MODEL_ID`: Hugging Face image-classification model id for AI-generated image detection.
- `AIDA_HF_MODEL_IDS`: comma-separated detector list for the visual ensemble.
- `AIDA_ALLOWED_ORIGINS`: JSON list of frontend origins allowed by CORS.
- `AIDA_MAX_UPLOAD_BYTES`: maximum accepted upload size.
- `AIDA_REQUIRE_ACCESS_TOKEN`: optional private-beta gate. Leave `false` for a public app; set `true` to require an access token for analysis, reports, metrics, and deletion.
- `AIDA_ACCESS_TOKEN_SHA256`: SHA-256 hex digest of the access token when token mode is enabled. Store the hash, not the raw token.
- `AIDA_RATE_LIMIT_ENABLED`: enable per-client rate limiting.
- `AIDA_RATE_LIMIT_WINDOW_SECONDS`: rate-limit window.
- `AIDA_RATE_LIMIT_MAX_REQUESTS`: general read/report/delete request limit per window.
- `AIDA_ANALYSIS_RATE_LIMIT_MAX_REQUESTS`: analysis-create request limit per window.
- `AIDA_METRICS_ENABLED`: expose Prometheus-style counters at `/metrics`. Keep this off publicly unless the route is protected by a reverse proxy or token mode.
- `AIDA_AUDIT_SALT`: deployment-specific salt used to hash client identifiers in audit logs.
- `AIDA_MEDIA_TTL_MINUTES`: how long queued encrypted media may remain before cleanup. Defaults to 15.
- `AIDA_JOB_TTL_HOURS`: how long completed metadata/report records remain. Defaults to 24.

## API

- `POST /analyses`: multipart form with either `file` or `url`, plus `consent_confirmed=true`.
- `GET /analyses/{id}`: job status and result when complete.
- `GET /analyses/{id}/report?format=json`: report JSON.
- `GET /analyses/{id}/report?format=pdf`: PDF report.
- `DELETE /analyses/{id}`: delete an analysis and any remaining stored media/report row early.
- `GET /ready`: readiness check for database and Redis when enabled.
- `GET /metrics`: Prometheus-style counters. For public deployments, protect this route at the reverse proxy or enable token mode.

When optional access-token protection is enabled, send `X-AIDA-Access-Token` from API clients and build the frontend with `VITE_REQUIRE_ACCESS_TOKEN=true`.

## Safety Boundaries

- Public URLs only. The fetcher rejects private, local, multicast, link-local, and reserved IPs.
- No login scraping, face search, doxxing, or private identity inference.
- Public attribution is limited to visible page metadata such as title, site name, author meta tags, and final URL.
- Sensitive previews are blurred by default in the frontend.
- Raw media is not returned by the API and is deleted after analysis.
- API responses include hardening headers, no-store caching on analysis endpoints, request IDs, rate limiting, and privacy-safe audit events.

## Optional Worker

For production-style processing:

```powershell
$env:AIDA_USE_RQ="true"
$env:AIDA_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/aida"
$env:AIDA_REDIS_URL="redis://localhost:6379/0"
python -m app.worker
```

The default local mode uses FastAPI background tasks so the app works without Redis/PostgreSQL.

`docker-compose.yml` provides local Postgres and Redis services when you want to test that path.

## Enabling The Visual Detector

The base install runs metadata, provenance, hashes, and forensic heuristics. For meaningful AI-image detection, install the ML extras and enable the model adapter:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
$env:AIDA_ENABLE_HF_MODEL="true"
$env:AIDA_HF_MODEL_IDS="buildborderless/CommunityForensics-DeepfakeDet-ViT,Ateeqq/ai-vs-human-image-detector,jacoballessio/ai-image-detect-distilled"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The default setup uses Community Forensics as the broad primary detector, plus two independently trained counter-experts. The primary runs on the original image, a center crop, controlled JPEG recompression, horizontal mirror, and social-media-style resize. Median, range, MAD, and IQR stability are recorded. Each model has its own conservative abstention band, and only calibrated stances are compared; raw score ranges remain diagnostic because classifier scales are not interchangeable. Treat the ensemble as one evidence layer, not a guarantee. A `likely_ai_generated` claim requires signed/generative provenance, independent non-model support, or unusually strong multi-model agreement with no real/human vote.

## Accuracy And Calibration Gate

No image detector can truthfully guarantee a correct answer for every uploaded photo, especially screenshots, crops, compressed social-media exports, and new generator families. This app is hardened around measurable calibration instead:

- Individual detector scores are reliability-weighted before aggregation.
- Detector-specific AI/real thresholds are used instead of treating every model score as equally calibrated.
- Low-resolution crops, screenshots, and heavily compressed exports cap confidence.
- Real/human-origin model votes and detector disagreement force `inconclusive` instead of a risky accusation.
- Deployment should be blocked unless a labeled golden set passes the safety gates.

Run the starter benchmark:

```powershell
cd backend
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe evaluate_goldens.py ..\test-artifacts\golden-manifest.example.json --enable-hf-model --max-real-fpr 0 --min-ai-recall 0.5 --max-high-confidence-error-rate 0
```

Before public launch, replace the starter manifest with a larger private calibration set: real phone/camera portraits, screenshots, cropped profile photos, edited/recompressed real photos, known AI images from multiple generators, and benign NSFW-like samples. Keep victim-sensitive calibration files private and ephemeral; do not commit them.

## Deployment Checklist

Before exposing this publicly:

1. Build the frontend with `npm run build`; the FastAPI backend serves `frontend/dist`.
2. Use PostgreSQL for `AIDA_DATABASE_URL`, Redis/RQ with `AIDA_USE_RQ=true`, and run at least one `python -m app.worker` process.
3. Set a persistent `AIDA_ENCRYPTION_KEY`; do not rely on the local in-memory fallback.
4. Set `AIDA_ALLOWED_ORIGINS` to the deployed frontend domain only.
5. Set `AIDA_AUDIT_SALT` to a long random value so audit identifiers are stable only inside this deployment.
6. Keep `AIDA_REQUIRE_ACCESS_TOKEN=false` for a public app. For a private beta, set it to `true`, generate a long random access token, and store only its SHA-256 in `AIDA_ACCESS_TOKEN_SHA256`.
7. Install `backend/requirements-ml.txt` and set `AIDA_ENABLE_HF_MODEL=true` plus the detector ensemble IDs.
8. Put the API behind HTTPS and a reverse proxy with request-size limits matching `AIDA_MAX_UPLOAD_BYTES`.
9. Keep TTLs short for sensitive media and verify logs do not contain uploaded media, raw metadata, or private URLs.
10. Add a real C2PA tool (`c2patool` or compatible executable) to the runtime if signed content credentials matter for launch.

When `AIDA_DEPLOYMENT_MODE=production`, the backend fails startup if the encryption key, server database, Redis/RQ worker mode, deployed CORS origin, rate limiting, or audit salt are missing. Access-token mode is optional for private beta deployments.

## Public Launch Gate

Do not treat the app as public-ready until these checks pass in the deployment environment:

1. `python -m pytest` passes in `backend` with `PYTHONPATH=.`.
2. `npm run lint` and `npm run build` pass in `frontend`.
3. `evaluate_goldens.py` passes against a private calibration set with real portraits, screenshots, recompressed images, and known AI samples.
4. `/ready` returns `database=ok` and `redis=ok` when `AIDA_USE_RQ=true`.
5. A live generated-image control returns `likely_ai_generated` or a documented calibrated abstention.
6. A live real-photo control is not falsely called `likely_ai_generated`.
7. Logs are sampled to confirm no raw media, raw private URLs, GPS metadata, or access tokens are emitted.
8. The deployed frontend origin is the only production CORS origin.
9. The reverse proxy enforces HTTPS, body-size limits, request timeouts, and abuse-rate controls.
10. A takedown/support page is published for victim resources, platform reporting links, and data-retention details.

## Enterprise Controls

Implemented in this repo:

- Optional access-token gate for private beta deployments.
- Per-client rate limiting with separate stricter limits for analysis creation.
- `/ready` checks for database and Redis availability.
- `/metrics` Prometheus-style counters.
- Privacy-safe structured audit events. Client identifiers are salted hashes; raw media and raw submitted URLs are not logged.
- Early delete endpoint for user-driven retention.
- Production startup validation and security headers.

Still expected from the deployment environment for a true enterprise rollout:

- HTTPS/TLS termination, WAF/CDN-level rate limiting, and request-size enforcement.
- SSO/OIDC/SAML if you later need named enterprise users, organization accounts, or admin dashboards.
- Centralized logs, metrics scraping, alerting, backups, and incident response.
- Legal/privacy review for target jurisdictions and abuse-report workflows.

## Docker Production Path

The root `Dockerfile` builds the React frontend, copies it into the FastAPI image, installs the optional ML detector dependencies by default, and runs as a non-root user.

```powershell
Copy-Item .env.production.example .env.production
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Edit .env.production:
# - POSTGRES_PASSWORD
# - AIDA_ENCRYPTION_KEY
# - AIDA_ALLOWED_ORIGINS
docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d
curl http://127.0.0.1:8000/health
```

The production compose file starts:

- `web`: FastAPI plus the built frontend.
- `worker`: RQ worker for analysis jobs.
- `postgres`: durable job/report metadata.
- `redis`: queue backend.

The first model-backed analysis may be slow while Hugging Face model weights are downloaded and cached. For a public deployment, choose a host with enough memory for PyTorch plus the configured mixture-of-experts detector panel.
The production compose file sets `HF_HOME=/data/huggingface` so model weights persist in the application data volume across restarts.

## Render Blueprint Deployment

This repo includes `render.yaml` for a Docker-based Render deployment. It provisions one public web service, one Render Postgres database, and one Render Key Value queue.

The Render web service runs both FastAPI and the RQ worker in one container through `python -m app.render_entrypoint`. This is intentional: the app stores sensitive uploads as encrypted short-lived blobs under `/data`, and Render persistent disks are attached to one service. Keeping the worker in the same service lets the API and worker share the same encrypted temp storage and Hugging Face model cache.

Deploy flow:

1. Push `main` to GitHub.
2. In Render, create a new Blueprint from `https://github.com/Devrajsinh-Jhala/DeepFake-MoE`.
3. Use the committed `render.yaml`.
4. Keep the generated `AIDA_ENCRYPTION_KEY` and `AIDA_AUDIT_SALT` values stable after first deploy.
5. After deploy, open `/ready`; it should report `database=ok` and `redis=ok`.
6. Run one generated-image control and one real-photo control before sharing the public URL.

The default Blueprint uses the `standard` web plan, a 20 GB persistent disk, `basic-256mb` Postgres, and `starter` Key Value. Increase the web plan if model inference is slow or the service approaches memory limits.

## Hugging Face Spaces Demo Deployment

For the least-friction public demo, use Hugging Face Spaces with the Docker SDK. Spaces CPU Basic is a better free fit for this ML-heavy app than most web-app free tiers because it provides enough RAM for the pretrained detector ensemble. The tradeoff is that default disk storage is ephemeral, so model weights and local SQLite state can be lost when the Space restarts.

Deploy flow:

```powershell
hf auth login
hf repo create YOUR_USERNAME/deepfake-moe --repo-type space --space_sdk docker --exist-ok
hf upload YOUR_USERNAME/deepfake-moe . --repo-type space --exclude ".git/*" ".cache/*" "backend/.data/*" "backend/.venv/*" "frontend/node_modules/*" "frontend/dist/*" "test-artifacts/*"
```

The README front matter sets `sdk: docker` and `app_port: 8000`, and the Docker image enables the Hugging Face detector ensemble by default. Use this path for demos and early public feedback. Use the Render/Docker Compose production paths when you need stable storage, queue durability, database backups, and stricter operations.
