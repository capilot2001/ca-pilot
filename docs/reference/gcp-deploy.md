# Deploying to Google Cloud

**Everything runs as one Cloud Run service.** FastAPI serves the API *and* the
built React bundle, so there is one image, one deploy, one URL, one console.

| Piece | Where it ends up |
|-------|------------------|
| Backend (FastAPI; OCR via the Cloud Vision API) | Cloud Run |
| Frontend (React + Vite, static after `npm run build`) | baked into the same image, served by FastAPI |
| Container image | Artifact Registry |
| Build | Cloud Build |

Three things fall away by collapsing it into one service:

- **No CORS.** Same origin, so `backend/app/main.py`'s `allow_origins=["*"]` —
  currently an open door to your client GST data — can be deleted outright
  rather than carefully maintained.
- **No `VITE_API_URL`.** `frontend/src/api.ts:6` falls back to `''` when the var
  is unset, which makes every call a relative `/api/...` — exactly right when
  the API is on the same host. The build-time-inlining trap disappears.
- **No second bill, no second CDN, no load balancer.** The SPA is ~200 KB of
  static files off a container you're already paying request-seconds for.

Cloud Run is also just the right runtime for this app: it **scales to zero**
(no traffic, no bill — unlike App Runner in `aws-deploy.md`, which bills
provisioned memory 24/7) and it **builds in the cloud on x86_64**, so the arm64
cross-compile and the multi-GB push over your home upload link both vanish.

The app is **stateless**: `COMPANY` lives in memory, uploads are processed and
discarded, exports stream straight back. No Cloud SQL, no bucket, no migrations.

Region: **`asia-south1`** (Mumbai). Lowest latency for you, everything used here
is available there. Keep Cloud Run, Artifact Registry and Cloud Build all in it —
mixing regions means paying egress between them.

> Want the frontend hosted separately anyway (CDN, custom domain, fast frontend
> iterations)? That's **Appendix A**. Still all Google Cloud — Firebase Hosting
> is the same GCP project and the same billing account, just a different console.

---

## Costs — read this before you start

Cloud Run has a real **always-free monthly tier** (approximately 2M requests,
180k vCPU-seconds, 360k GiB-seconds — confirm at
https://cloud.google.com/run/pricing). Scaled to zero between uses, a
low-traffic office tool realistically lands at **$0–3/month**, nearly all of it
Artifact Registry storage for the image.

Two things take you out of that:

- **`--min-instances 1`** (keeping one instance warm to kill cold starts). You
  are then billed for idle CPU and memory around the clock — order of
  **$10–20/month** at 2 vCPU / 4 GiB. That's an estimate; price it at
  https://cloud.google.com/products/calculator before turning it on. Leave it at
  0 unless a live demo forces your hand.
- **The image.** Now that OCR is an API call the image is a few hundred MB, not
  several GB, but Artifact Registry still bills per GB-month and old tags add
  up. Prune (cheatsheet at the bottom).
- **Cloud Vision.** Billed per page/image after the first 1,000 units a month
  (about $1.50 per 1,000 beyond that for DOCUMENT_TEXT_DETECTION). Only
  *scanned* invoices call it — digital PDFs are read with PyMuPDF and cost
  nothing.

New accounts get **$300 in credits for 90 days**. Billing must still be enabled
on the project — Cloud Run refuses to deploy without it, even inside free tier.

---

## Step 0 — Account and project setup (20 min, once)

### 0.1 Create the project
Console → project dropdown → **New Project** → name it `finance-tally`. Note the
**Project ID** it generates — that string, not the display name, is what you use
everywhere below.

### 0.2 Link billing
**Billing** → link the project to your billing account.

### 0.3 Set a budget alert (do not skip)
**Billing** → **Budgets & alerts** → **Create budget** → scope to this project →
amount **$20** → alerts at 50/90/100% → your email.

This is the most important step in the guide. It's what stops a mistake from
becoming a bill.

### 0.4 Install and configure the CLI
```bash
brew install --cask google-cloud-sdk
gcloud init          # log in, pick the project
```

Set defaults so you stop typing them:
```bash
export PROJECT_ID=$(gcloud config get-value project)
export REGION=asia-south1
export IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/finance/ledgerflow

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

### 0.5 Enable the APIs
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

Takes a minute. `gcloud config list` to confirm you're pointed at the right
project.

---

## Step 1 — Two small code changes

> **Already applied to this repo** — recorded here so you know what changed and
> why. Both are one-time; after them the repo builds and deploys as a unit.

### 1.1 Let FastAPI serve the React bundle
Append to the **end** of `backend/app/main.py` — it must come after every route,
because it's a catch-all mount that would otherwise swallow `/api/*`:

```python
# ---- static frontend ------------------------------------------------------
# The React bundle is copied to app/static at image build time (see Dockerfile)
# and served from this same service, so the browser talks to one origin: no
# CORS, and api.ts's empty VITE_API_URL fallback resolves to relative /api URLs.
# Mounted last — this is a catch-all and would shadow the /api routes above it.
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_static = Path(__file__).parent / "static"
if _static.is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="ui")
```

The `if` matters: without the built bundle present (local dev, where Vite serves
the UI on :5180 and proxies `/api` to :8077) the mount is skipped and nothing
breaks.

`html=True` serves `index.html` at `/`. That's sufficient here because the
frontend has **no client-side router** — `frontend/package.json` depends only on
`react` and `react-dom`, and `App.tsx` is a single shell gated by login. If you
ever add `react-router`, deep links like `/invoices/3` will 404 and you'll need
an explicit catch-all route returning `index.html`.

### 1.2 Drop CORS
Same origin now, so `backend/app/main.py:23-26` is dead weight and an open door.
Delete the block:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
```

...and its `from fastapi.middleware.cors import CORSMiddleware` import.

**Keep it if you still run the Vite dev server against a deployed backend** —
that is genuinely cross-origin. If so, narrow it to
`allow_origins=["http://localhost:5180"]` rather than `["*"]`.

---

## Step 2 — One Dockerfile that builds both halves

> **Already applied.** `backend/Dockerfile` has **moved to `./Dockerfile`** (repo
> root) and gained a Node stage. The move is required, not cosmetic:
> `gcloud builds submit --tag` runs `docker build .` against the root of the
> uploaded source and looks for the Dockerfile *there*, so a Dockerfile left in
> `backend/` would simply not be found. Stage 1 needs to see `frontend/` anyway.

```dockerfile
# ---- stage 1: build the React bundle --------------------------------------
FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# No VITE_API_URL on purpose: api.ts falls back to '' and every call becomes a
# relative /api/... — correct, because the API is served from this same origin.
RUN npm run build

# ---- stage 2: the API, with the bundle inside it --------------------------
FROM python:3.11-slim
WORKDIR /app

# DejaVu only, for the rupee glyph in the reconciliation PDF. The OpenCV/Paddle
# libs went out with PaddleOCR.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=ui /ui/dist ./app/static

ENV PORT=8080
EXPOSE 8080

# Single worker, matching --concurrency 1. OCR is a network call now, not an
# in-process model, so this is no longer a memory ceiling.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 120"]
```

The build context is the repo root, so `docker build` and `gcloud builds submit`
are both run from `~/Developer/finance`, never from `backend/`.

### 2.1 Keep junk — and client data — out of the upload
> **Already applied** — `.gcloudignore` and `.dockerignore` exist at the repo root.

`gcloud builds submit` tars the source directory and ships it to Cloud Build.
From the repo root that would sweep up `frontend/node_modules`, `backend/.venv`,
and **every real client invoice PDF sitting at the root**. Write both ignore
files explicitly:

```bash
cd ~/Developer/finance
cat > .gcloudignore <<'EOF'
.git
.DS_Store
__pycache__/
*.pyc
backend/.venv/
backend/verify_e2e.py
frontend/node_modules/
frontend/dist/
# client documents and working files — must never leave this machine
*.pdf
*.xlsx
*.pptx
*.jpg
*.png
EOF
cp .gcloudignore .dockerignore
```

`.gcloudignore` controls what gets uploaded; `.dockerignore` controls what the
build can see. They want the same list, hence the `cp`.

**Watch the pattern depth.** `.gcloudignore` uses *gitignore* semantics, where a
slash-less pattern matches at every level — a bare `package-lock.json` line also
eats `frontend/package-lock.json` and breaks stage 1's `npm ci`. Anchor it as
`/package-lock.json`. Comments must also sit on their own line; gitignore has no
trailing-comment syntax, so `/foo  # why` is read as a literal pattern.

> gcloud falls back to `.gitignore` when there's no `.gcloudignore` — don't rely
> on that here. The root `.gitignore` doesn't list the client PDFs, so the
> fallback would upload them.

---

## Step 3 — Build and deploy

### 3.1 Create the Artifact Registry repository
```bash
gcloud artifacts repositories create finance \
  --repository-format=docker \
  --location=$REGION \
  --description="LedgerFlow images"
```

### 3.2 Build
```bash
cd ~/Developer/finance
gcloud builds submit --tag $IMAGE:v1 --timeout=3600s --region=$REGION
```

`--timeout=3600s` is harmless insurance but no longer load-bearing: dropping the
Paddle wheels took the build from 15–30 minutes to **2–4 minutes**, well inside
Cloud Build's 10-minute default. Cloud Build starts clean each run, so there's
no layer cache to speed up reruns.

Verify:
```bash
gcloud artifacts docker images list $IMAGE
```

> No `docker buildx --platform linux/amd64`, no local Docker at all. Cloud Build
> is x86_64, so the arm64 footgun from the AWS path can't happen.

### 3.3 Deploy
```bash
gcloud run deploy ledgerflow \
  --image $IMAGE:v1 \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 4Gi \
  --cpu 2 \
  --concurrency 1 \
  --timeout 900 \
  --max-instances 3 \
  --min-instances 0 \
  --cpu-boost \
  --set-env-vars "COMPANY_NAME=Narsingh Prasad Bishnu Prasad,COMPANY_GSTIN=21AAAHN9743B1ZL,COMPANY_STATE_CODE=21,COMPANY_PAN=AAAHN9743B"
```

Why each flag is what it is:

| Flag | Reason |
|------|--------|
| `--port 8080` | Matches `ENV PORT=8080`. Cloud Run also injects `$PORT`, which the `CMD` reads — correct either way. |
| `--memory 4Gi` | Generous now that no OCR model is loaded in-process — the working set is PyMuPDF rasterising pages at 300 DPI plus the encoded PNGs held for a batch. **Cloud Run's writable filesystem is tmpfs and counts against this limit**, so leave headroom. 1–2Gi would likely do; 4Gi is kept because it costs nothing while idle and a 50-file batch is the stress case. |
| `--cpu 2` | Required to exceed 4 GiB anyway. Extraction is now I/O-bound on the Vision call rather than CPU-bound, so this matters less than it did. |
| `--concurrency 1` | The Dockerfile runs a **single uvicorn worker**. This was forced by Paddle's memory use; with OCR out of process it is now just a conservative default, and raising it is the cheapest way to serve more users — see 3.6. |
| `--timeout 900` | 15 min per request; a batch of scans can run minutes. Max is 3600. |
| `--max-instances 3` | Caps the blast radius of a runaway loop. |
| `--min-instances 0` | Scale to zero, ~$0 idle. Costs a cold start (see 3.5). |
| `--cpu-boost` | Extra CPU during startup, free. Shortens cold starts. |
| `--allow-unauthenticated` | Public URL. Read "Before anyone else uses this" before real client data goes near it. |

Capture the URL:
```bash
export APP_URL=$(gcloud run services describe ledgerflow \
  --region $REGION --format='value(status.url)')
echo $APP_URL
```

### 3.4 Smoke-test
```bash
open $APP_URL                    # the React app itself
curl $APP_URL/api/health         # → {"status":"ok"}

# digital PDF — fast path, PyMuPDF text layer, no OCR
curl -F "files=@Mamta Industries.pdf" $APP_URL/api/extract | head -c 500

# scanned image — exercises the Cloud Vision path. ~1s per page, no warm-up.
curl -F "files=@first.jpg" $APP_URL/api/extract | head -c 500
```

Logs when something 500s:
```bash
gcloud run services logs read ledgerflow --region $REGION --limit 50
```

### 3.5 Cold starts, and the Vision API prerequisites
Scaled to zero, the first request after idle pays to pull and start the
container — now a few hundred MB rather than multi-GB, so this is quick. There
are no model weights to download on the first scan any more: `ocr.py` lazy-builds
a Vision client and the model lives on Google's side. The old advice to bake
PaddleOCR's weights into an image layer no longer applies and has been removed.

Two things must be true on the project or every scan fails:

```bash
# 1. the API has to be enabled
gcloud services enable vision.googleapis.com

# 2. the runtime service account has to be able to call it. A service account
#    belonging to this project needs no extra role; confirm with a real scan.
gcloud run services describe ledgerflow --region $REGION \
  --format='value(spec.template.spec.serviceAccountName)'
```

Credentials themselves need no configuration: Cloud Run hands the container
Application Default Credentials for its runtime service account, which is what
`vision.ImageAnnotatorClient()` picks up. If scans come back
`EXTRACTION_FAILED` mentioning credentials or `PERMISSION_DENIED`, it is one of
those two, not the code.

### 3.5a Gemini, the primary invoice reader

`llm_extract.py` reads each page with Gemini on **Vertex AI** — same project,
same Application Default Credentials, no API key. Unlike Vision it does need a
role granted explicitly:

```bash
gcloud services enable aiplatform.googleapis.com

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$(gcloud projects describe $PROJECT \
      --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

**Neither is required for the app to work.** Without them the reader turns
itself off on its first call and every invoice falls back to `parser.py`, which
is what read them before. The tell is the "OCR:" line on an invoice card: with
the reader working it says `google-vision + gemini-2.5-flash`, without it just
`google-vision`.

Knobs, all optional: `LEDGERFLOW_LLM=0` switches the reader off,
`LEDGERFLOW_LLM_MODEL` picks a different model, `LEDGERFLOW_LLM_LOCATION` a
different Vertex endpoint (default `global`).

Cost is roughly ₹0.15–0.20 per invoice on `gemini-2.5-flash` (about 3k input
tokens for the page image, prompt and OCR text, and a few hundred out), so a
thousand invoices a month sits well inside the ₹2,000 budget. A quota blip
comes back as `429 RESOURCE_EXHAUSTED`; that is retried with backoff and then
falls back to the parser for that one invoice, so a batch never fails on it.

### 3.6 Two limits worth knowing before they surprise you
- **32 MiB request body cap.** Cloud Run rejects larger uploads outright. Your
  invoice PDFs run ~300–600 KB, so ~50 files per call is the practical ceiling.
  Upload in smaller batches.
- **`--concurrency 1` means queueing is real.** Three simultaneous users with
  `--max-instances 3` is fine; ten is not. Raise max-instances, not concurrency —
  concurrency is pinned to 1 by that single uvicorn worker.

### 3.7 Redeploying later
```bash
cd ~/Developer/finance
gcloud builds submit --tag $IMAGE:v2 --timeout=3600s --region=$REGION
gcloud run deploy ledgerflow --image $IMAGE:v2 --region $REGION
```

New tag each time rather than overwriting `:v1`. Cloud Run keeps every revision,
so rollback is one command:
```bash
gcloud run revisions list --service ledgerflow --region $REGION
gcloud run services update-traffic ledgerflow \
  --to-revisions <OLDER_REVISION>=100 --region $REGION
```

**The one real cost of the single-service design:** a CSS tweak rebuilds the
whole image. That used to mean a 20-minute build; without the Paddle wheels it
is 2–4 minutes, so batching UI deploys matters much less than it did.

---

## Step 4 — End-to-end check

1. Open `$APP_URL`, log in (`admin` / `123456`).
2. Company bar populates → `GET /api/config` is working, same-origin.
3. Upload a **digital PDF** (`Mamta Industries.pdf`) → invoice card appears.
4. Upload a **scanned JPEG** (`first.jpg`) → exercises the Cloud Vision path.
5. Download a vouchers XLSX export → file downloads.
6. Import `GSTR-2A-sample.xlsx`, run reconcile.
7. Import the XLSX/XML into TallyPrime to confirm nothing broke in transit.

| Symptom | Cause |
|---------|-------|
| Blank page, 404 at `/` | The bundle didn't make it into the image. Check `COPY --from=ui` and that `frontend/dist/` isn't excluded by `.dockerignore` *inside* the ui stage (it isn't in the list above — the stage builds it fresh). |
| UI loads, every API call 404s | The static mount was added **before** the routes in `main.py` and is shadowing `/api/*`. It must be last. |
| 403 with `Forbidden` HTML | Service isn't public. Redeploy with `--allow-unauthenticated`. |
| 503 / "no healthy upstream" | Container failed to start. `gcloud run services logs read ledgerflow --region $REGION`. |
| 504 after ~15 min | Batch exceeded `--timeout 900`. Fewer files, or raise it (max 3600). |
| "memory limit exceeded" mid-OCR | Raise `--memory`, and bake the models in (3.5). |
| Cloud Build `TIMEOUT` | You dropped `--timeout=3600s`. |

---

## Before anyone else uses this

Three things that are fine for a demo and not fine in production:

**The login is fake.** `frontend/src/auth.tsx:24` compares against
`admin`/`123456` in browser JavaScript, and the backend has no auth at all —
anyone with the URL can POST invoices directly and read client GST data back.
Two Google-native fixes:
- **Identity-Aware Proxy** in front of Cloud Run — no code, you allowlist
  specific Google accounts. Needs a load balancer, so it costs (~$18/mo).
- **Firebase Auth** + a FastAPI dependency verifying the ID token on every
  request. Free, more code. Firebase Auth is part of this same GCP project.

**Config is process-global.** `COMPANY` in `backend/app/config.py:120` is one
shared mutable object. With `--max-instances 3`, two users on different
instances see different company config, and one user's `POST /api/config`
changes the other's exports. Single user: fine. Multi-client CA office: config
has to move into the request (header or body field) or into Firestore.

**Client invoices are in the repo.** `~/Developer/finance` has real client PDFs
(`KEDIYA STEEL…`, `SUNIL HARDWARE…`, `Vindhya Construction…`) untracked at the
root, and the root `.gitignore` doesn't cover them. Step 2.1's `.gcloudignore`
keeps them out of Cloud Build; do the same for `.gitignore` before this repo
goes near GitHub.

---

## Cost control cheatsheet

```bash
# What's running
gcloud run services list --region $REGION

# Hard stop: delete the service (one command to redeploy from the image later)
gcloud run services delete ledgerflow --region $REGION

# Softer: cap at zero instances — URL stays, requests fail fast, bill is nil
gcloud run services update ledgerflow --region $REGION --max-instances 0

# Artifact Registry bills per GB-month, so old tags add up. Prune them.
gcloud artifacts docker images list $IMAGE --include-tags
gcloud artifacts docker images delete $IMAGE:v1 --delete-tags

# Where the money went: Console → Billing → Reports, filtered to this project
```

Cloud Run, Artifact Registry storage, and Cloud Build minutes are the only three
lines you should ever see.

---

## Map

```text
~/Developer/finance                     ← build context is the repo ROOT
  ├─ frontend/  ─┐
  └─ backend/   ─┴─ gcloud builds submit --timeout=3600s
                        │  stage 1 (node)   npm run build  → dist/
                        │  stage 2 (python) pip install    + COPY dist → app/static
                        ▼
     Artifact Registry: asia-south1-docker.pkg.dev/<project>/finance/ledgerflow:v1
                        ▼
     Cloud Run "ledgerflow"  →  https://ledgerflow-xxxx.a.run.app
                                   ├─ /            → React SPA
                                   └─ /api/*       → FastAPI ─→ Cloud Vision
                                   (scales to zero)
```

---

## The whole thing, once the Step 1–2 edits are in

```bash
export PROJECT_ID=$(gcloud config get-value project) REGION=asia-south1
export IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/finance/ledgerflow

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create finance --repository-format=docker --location=$REGION

cd ~/Developer/finance
gcloud builds submit --tag $IMAGE:v1 --timeout=3600s --region=$REGION
gcloud run deploy ledgerflow --image $IMAGE:v1 --region $REGION \
  --allow-unauthenticated --port 8080 --memory 4Gi --cpu 2 --concurrency 1 \
  --timeout 900 --max-instances 3 --cpu-boost

export APP_URL=$(gcloud run services describe ledgerflow --region $REGION --format='value(status.url)')
curl $APP_URL/api/health && open $APP_URL
```

---

# Appendix A — If you'd rather host the frontend separately

Reasons you might: you want a **custom domain with a CDN**, or you're iterating
on the UI often and want to skip the backend rebuild per CSS change. (That
argument is much weaker now the whole image builds in 2–4 minutes.)

All three options below are still entirely Google Cloud, billed to this same
project. All three reintroduce **two origins**, so keep the CORS middleware from
Step 1.2 and narrow `allow_origins` to the frontend URL, and set `VITE_API_URL`
to the Cloud Run URL at build time (`api.ts` inlines it — changing it means
rebuilding, not editing a setting).

### A1 — Firebase Hosting (simplest, effectively free)
Global CDN, free HTTPS, generous free tier. Same GCP project — add Firebase to
it at https://console.firebase.google.com via **Add project → existing project**.

```bash
npm install -g firebase-tools
firebase login
cd ~/Developer/finance/frontend
firebase init hosting     # public dir: dist | SPA: Yes | overwrite index.html: No
VITE_API_URL=$APP_URL npm run build
firebase deploy --only hosting
```
Gives `https://<project-id>.web.app`. Redeploy = those last two commands.
List **both** `.web.app` and `.firebaseapp.com` in `allow_origins` — Firebase
serves on both.

### A2 — A second Cloud Run service (one console, fast UI builds)
Keeps you in Cloud Run only. A tiny nginx image with the `dist/` folder builds
in ~1 minute, so UI iteration is quick while the backend sits untouched. Costs a second service (still scale-to-zero, still ~$0) and one
extra `gcloud run deploy` per frontend change.

### A3 — Cloud Storage + external ALB + Cloud CDN
A proper CDN with a custom domain, but the global external load balancer is a
fixed **~$18/month** whether or not anyone visits. Only worth it if you need a
custom domain *and* CDN behaviour Firebase Hosting can't give you. For this app,
skip it.
