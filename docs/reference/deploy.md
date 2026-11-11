# Deploy for free

This app is two services:

| Piece | Stack | Free host |
|-------|--------|-----------|
| **Frontend** | React + Vite | [Vercel](https://vercel.com) |
| **Backend** | FastAPI + Cloud Vision OCR | [Google Cloud Run](https://cloud.google.com/run) (recommended) or [Render](https://render.com) |

The browser talks **directly** to the backend URL (CORS is already open). Do **not** proxy `/api` through Vercel — OCR can take longer than Vercel’s hobby timeout.

OCR is a Cloud Vision API call, so the container itself stays small — **1 GB RAM** is comfortable. What it does need is credentials: the host must supply a Google service account (Application Default Credentials) and have `vision.googleapis.com` enabled on the project. Digital text PDFs never call out at all — they use PyMuPDF only.

---

## Prerequisites

1. GitHub repo with this project pushed.
2. Accounts (all free to start):
   - [Vercel](https://vercel.com/signup)
   - One backend host: [Google Cloud](https://console.cloud.google.com) **or** [Render](https://render.com/register)
3. Local tools only if you use Cloud Run CLI: [gcloud CLI](https://cloud.google.com/sdk/docs/install)

---

## Step 1 — Deploy the backend (pick one)

### Option A — Google Cloud Run (best free fit for OCR)

Always-free monthly quota (within limits), scales to zero when idle, and you can set **2 GiB** memory.

1. Create a Google Cloud project and enable billing (required; Always Free + $300 new-account credit apply within quotas).
2. Install and log in:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
   ```
3. From the repo root, deploy the `backend/` folder:
   ```bash
   cd backend
   gcloud run deploy finance-api \
     --source . \
     --region asia-south1 \
     --allow-unauthenticated \
     --memory 2Gi \
     --cpu 1 \
     --timeout 300 \
     --max-instances 2 \
     --set-env-vars "COMPANY_GSTIN=21AAAHN9743B1ZL,COMPANY_STATE_CODE=21"
   ```
4. When it finishes, copy the service URL, e.g.  
   `https://finance-api-xxxxx-xx.a.run.app`
5. Smoke-test:
   ```bash
   curl https://YOUR_CLOUD_RUN_URL/api/health
   # → {"status":"ok"}
   ```

**Notes**

- First request that needs OCR downloads models and can be slow (cold start).
- Stay in a low-traffic region and keep `max-instances` small to stay inside free quota.
- Optional company defaults: `COMPANY_NAME`, `COMPANY_GSTIN`, `COMPANY_STATE_CODE`, `COMPANY_PAN`, `COMPANY_STOCK` (see `backend/app/config.py`).

---

### Option B — Render (simpler UI, tighter free limits)

1. Go to [render.com](https://render.com) → **New** → **Web Service**.
2. Connect the GitHub repo.
3. Settings:

   | Field | Value |
   |-------|--------|
   | Root Directory | `backend` |
   | Runtime | Docker |
   | Dockerfile Path | `./Dockerfile` (repo root — it moved out of `backend/`; set Root Directory to `.`) |
   | Instance type | Free (or the cheapest paid if free OOMs) |
   | Health Check Path | `/api/health` |

4. Add env vars if you want defaults (`COMPANY_GSTIN`, etc.).
5. Deploy → copy the URL, e.g. `https://finance-api.onrender.com`.
6. Test: `curl https://YOUR_RENDER_URL/api/health`

**Caveats**

- Free instances **sleep** after ~15 minutes idle; first wake + OCR can take a minute.
- If scans return `EXTRACTION_FAILED` mentioning credentials, the host has no Application Default Credentials — mount a service-account key and set `GOOGLE_APPLICATION_CREDENTIALS`. On Cloud Run (Option A) the runtime service account supplies them automatically.
- Digital PDFs (text layer) usually work even when scanned OCR does not.

---

### Option C — Railway (quick trial credit)

1. [railway.app](https://railway.app) → New Project → Deploy from GitHub.
2. Set root to `backend`, use the Dockerfile.
3. Set memory as high as the trial allows; start command is already in the Dockerfile.
4. Generate a public domain → test `/api/health`.

Trial credits run out; not a permanent free host.

---

## Step 2 — Deploy the frontend on Vercel

1. Push your latest code (including `frontend/src/api.ts`, which reads `VITE_API_URL`).
2. Go to [vercel.com/new](https://vercel.com/new) → import the GitHub repo.
3. Configure the project:

   | Field | Value |
   |-------|--------|
   | Framework Preset | Vite |
   | Root Directory | `frontend` |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |
   | Install Command | `npm install` |

4. **Environment Variables** → add:

   | Name | Value |
   |------|--------|
   | `VITE_API_URL` | Your backend URL with **no** trailing slash, e.g. `https://finance-api-xxxxx-xx.a.run.app` |

5. Deploy.
6. Open the Vercel URL → log in (`admin` / `123456` — client-side gate only; change this before sharing publicly).

Redeploy the frontend whenever you change `VITE_API_URL` (Vite bakes env vars in at build time).

---

## Step 3 — End-to-end check

1. Frontend loads and login works.
2. Company bar shows config from the backend (`GET /api/config`).
3. Upload a **digital PDF** first (fast path, no Vision call).
4. Then try a scanned JPEG/PNG (loads OCR models; first call is slow).
5. Download a masters/vouchers export.

If the UI loads but every API call fails:

- Confirm `VITE_API_URL` has no trailing slash and uses `https://`.
- Open DevTools → Network → check the request host is your backend, not `*.vercel.app/api/...`.
- Hit `/api/health` on the backend URL in the browser.

---

## Local reminder (unchanged)

```bash
# Backend
cd backend && ./run.sh          # http://127.0.0.1:8077

# Frontend — leave VITE_API_URL unset; Vite proxies /api → 8077
cd frontend && npm install && npm run dev   # http://localhost:5180
```

---

## Optional hardening (still free)

- Restrict CORS in `backend/app/main.py` from `"*"` to your Vercel domain once stable.
- Replace the hardcoded login in `frontend/src/auth.tsx` before public use.
- On Cloud Run, set request timeout ≥ 300s for large scanned batches.
- Prefer digital PDFs in production free deploys; OCR is the expensive path.

---

## Quick reference

```text
GitHub repo
   ├─ backend/   →  Cloud Run / Render / Railway   →  https://….a.run.app
   └─ frontend/  →  Vercel (Root = frontend)      →  https://….vercel.app
                      └─ env: VITE_API_URL = backend URL
```
