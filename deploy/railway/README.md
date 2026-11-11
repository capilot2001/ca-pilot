# Railway — the server (API + in-process OCR)

Railway hosts the **stateful** service: the FastAPI server, which in Phase-0
also runs the OCR reading pipeline in-process, plus the SQLite volume.

## Service
- **Build:** Dockerfile `server/Dockerfile`, **root directory = repo root**
  (`Codebase/v2-finance`). The image needs `shared/`, `services/ocr/` and
  `server/` together, so the build context must be the root, not `server/`.
- **Start:** taken from the Dockerfile `CMD` — `uvicorn app.main:app` binding
  `$PORT`, which Railway injects. No start command override needed.

## Volume (required — ADR-0007)
Attach a volume and mount it at **`/data`**. SQLite lives there; without it the
client list is wiped on every redeploy (the container FS is ephemeral).

## Variables
Set these on the service (see `../env/server.env.example` for the full list):

| Variable | Value |
|---|---|
| `LEDGERFLOW_DB` | `/data/ledgerflow.db` (on the mounted volume) |
| `CORS_ORIGINS` | the client's URL, e.g. `https://ledgerflow.vercel.app` |
| `OCR_MODE` | `in_process` |
| `GOOGLE_APPLICATION_CREDENTIALS` | path to a mounted GCP service-account key |
| `GOOGLE_CLOUD_PROJECT` | your GCP project id |

The service account needs `roles/aiplatform.user` (Gemini) and access to Cloud
Vision; `aiplatform.googleapis.com` and `vision.googleapis.com` must be enabled.

Moving off Railway is a change here + the variables — never a code change
(ADR-0002).
