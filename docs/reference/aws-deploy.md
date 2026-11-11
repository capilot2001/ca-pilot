# Deploying to AWS

> **Stale path warning.** The Dockerfile has since moved to the **repo root**
> (`./Dockerfile`) and now builds the frontend in as well — see `gcp-deploy.md`.
> Every `cd ~/Developer/finance/backend` + `docker build .` below should be run
> from `~/Developer/finance` instead. The resulting image serves the UI too, so
> the separate Amplify step in Step 2 becomes optional.

Two pieces, two AWS services:

| Piece | What it is | AWS service |
|-------|-----------|-------------|
| **Backend** | FastAPI, Docker; OCR via the Google Cloud Vision API | **ECR** (image registry) → **App Runner** (runs it) |
| **Frontend** | React + Vite, static files after `npm run build` | **Amplify Hosting** (or S3 + CloudFront) |

> **Google credentials are required even on AWS.** OCR calls the Cloud Vision
> API, and outside Google Cloud there are no ambient Application Default
> Credentials. Create a GCP service account with Vision access, download its JSON
> key, ship it to the container as a secret (App Runner: a secret env var written
> to a file at start; ECS: a mounted secret), and set
> `GOOGLE_APPLICATION_CREDENTIALS` to that path. Without it every scanned invoice
> returns `EXTRACTION_FAILED`. Digital PDFs are unaffected — they never call out.

App Runner is the closest AWS equivalent to Cloud Run: give it a container image
and a port, it gives you an HTTPS URL, TLS cert, and autoscaling. No load
balancer, VPC, or ECS task definition to write.

The app is **stateless** — `COMPANY` lives in memory, uploads are processed and
discarded, exports stream straight back. No RDS, no S3 bucket for data, no
migrations. That keeps this simple.

Pick region **`ap-south-1`** (Mumbai) — lowest latency for you, and everything
here is available there. Use the same region for every step.

---

## Costs — read this before you start

App Runner **does not scale to zero.** You pay for provisioned memory 24/7 even
with no traffic. At 1 vCPU / 2 GB that is roughly **$10–15/month** idle, plus
active-CPU charges while requests run. Amplify Hosting for the frontend is
pennies at this traffic level.

Check the live numbers at https://aws.amazon.com/apprunner/pricing/ before
committing — prices change.

If that is too much for a demo, you have two escape hatches:

- **Pause the App Runner service** when you're not demoing (console → Actions →
  Pause). Paused services bill nothing for compute; resume takes ~1 minute.
- **Lambda with a container image** scales to zero and costs ~$0 idle. Now that
  OCR is an API call rather than an in-process model, cold starts are just the
  image pull, so this is a more reasonable option than it used to be.

New AWS accounts now sign up under the credits-based free tier rather than the
old 12-month one. Whatever credits you got, **set a budget alarm in Step 0.2** —
this is the single most important step in the whole guide.

---

## Step 0 — Account setup (30 min, do this once)

### 0.1 Secure the root account
1. Sign in as root → **IAM** → enable **MFA** on the root user.
2. Never use root again after this section.

### 0.2 Set a budget alarm (do not skip)
**Billing and Cost Management** → **Budgets** → **Create budget** →
*Use a template* → **Monthly cost budget** → set to e.g. **$20** → your email.

You'll get an email at 85% and 100% of that. This is what stops a mistake from
becoming a bill.

### 0.3 Create a user for daily work
**IAM** → **Users** → **Create user** → name `deploy` → *Attach policies
directly*.

For a solo project, `AdministratorAccess` is the pragmatic choice. (The
least-privilege set here would be `AmazonEC2ContainerRegistryFullAccess` +
`AWSAppRunnerFullAccess` + `AdministratorAccess-Amplify` + IAM role creation —
tighten to that later if this ever becomes a real product.)

Then **Security credentials** → **Create access key** → *Command Line Interface*
→ copy the **Access key ID** and **Secret access key**. The secret is shown
once.

### 0.4 Install and configure the CLI
```bash
brew install awscli
aws configure
# AWS Access Key ID:     <paste>
# AWS Secret Access Key: <paste>
# Default region name:   ap-south-1
# Default output format: json
```

Verify:
```bash
aws sts get-caller-identity
```
Note the `Account` value — that 12-digit number is your `ACCOUNT_ID`, used
below.

---

## Step 1 — Backend to ECR + App Runner

### 1.1 Add a `.dockerignore`
Keeps the 500 MB `.venv` and stray files out of the build context:

```bash
cd ~/Developer/finance/backend
cat > .dockerignore <<'EOF'
.venv
__pycache__
*.pyc
verify_e2e.py
package-lock.json
EOF
```

### 1.2 Create the ECR repository
```bash
aws ecr create-repository \
  --repository-name finance-api \
  --region ap-south-1
```
Copy the `repositoryUri` from the output. It looks like
`123456789012.dkr.ecr.ap-south-1.amazonaws.com/finance-api`.

### 1.3 Log Docker into ECR
```bash
export ACCOUNT_ID=123456789012        # yours, from step 0.4
export REGION=ap-south-1
export ECR=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $ECR
```

### 1.4 Build for x86_64 — this is the step people get wrong
Your Mac is **arm64**. App Runner runs **x86_64 only**. A default `docker build`
here produces an arm64 image that App Runner accepts and then fails to start,
with an unhelpful error. Always pass `--platform`:

```bash
cd ~/Developer/finance/backend
docker buildx build --platform linux/amd64 -t $ECR/finance-api:v1 --push .
```

The image is a few hundred MB (it was multi-GB before OCR moved out of process),
but it is still cross-compiling and pushing over your home upload link. Later
pushes only send changed layers and are much faster.

> If the upload is unbearable, build in AWS instead with **CodeBuild** — the
> push to ECR then happens inside AWS at datacenter speed. Worth setting up only
> if you'll be redeploying often.

Verify it landed:
```bash
aws ecr list-images --repository-name finance-api --region $REGION
```

### 1.5 Create the App Runner service (console)
Use the console for this one — it creates the ECR access IAM role for you, which
is fiddly over the CLI.

**App Runner** → **Create service**:

| Field | Value |
|-------|-------|
| Repository type | **Container registry** → Amazon ECR |
| Container image URI | `<ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/finance-api:v1` |
| Deployment trigger | **Manual** (Automatic redeploys on every ECR push) |
| ECR access role | **Create new service role** |
| Service name | `finance-api` |
| Virtual CPU / memory | **1 vCPU / 1 GB** — no OCR model is loaded in-process; this covers PyMuPDF page rasterising |
| Port | **8080** (matches `ENV PORT=8080` in your Dockerfile) |
| Health check protocol | **HTTP**, path `/api/health` |
| Auto scaling | Max size **2**, max concurrency **1** |

Under **Environment variables**, add your company defaults (all optional — they
override the values in `backend/app/config.py`):

```
COMPANY_NAME=Narsingh Prasad Bishnu Prasad
COMPANY_GSTIN=21AAAHN9743B1ZL
COMPANY_STATE_CODE=21
COMPANY_PAN=AAAHN9743B
```

**Max concurrency 1** is a conservative default carried over from when OCR ran
in-process. Extraction is I/O-bound on the Vision call now, so raising it is
reasonable if you have several users.

Create. First deploy takes ~5–10 minutes.

### 1.6 Smoke-test
```bash
curl https://<your-id>.ap-south-1.awsapprunner.com/api/health
# → {"status":"ok"}
```

Then a real extraction with a digital PDF (fast path, no OCR):
```bash
curl -F "files=@../Mamta Industries.pdf" \
  https://<your-id>.ap-south-1.awsapprunner.com/api/extract | head -c 500
```

Then a scanned image (`first.jpg`) to exercise the Cloud Vision path — about a
second per page, with no model warm-up.

### 1.7 The request-timeout caveat
App Runner enforces a per-request timeout (120 seconds by default) that you have
much less control over than Cloud Run's. A big batch of scanned invoices in one
`/api/extract` call can exceed it and return a 504 even though the backend is
still working.

Mitigations, cheapest first:
1. **Upload in smaller batches** from the UI — a few files per call.
2. There is no model cache to warm any more — the old "bake the OCR weights into
   the image" step is gone with PaddleOCR.
3. If you genuinely need long requests, move to **ECS Fargate behind an ALB**,
   where the idle timeout is yours to set (up to 4000 s). That's a real step up
   in setup complexity — task definition, VPC, security groups, target group,
   ACM certificate — and costs more (~$35/mo Fargate + ~$16/mo ALB). Only go
   there if 1 and 2 aren't enough.

### 1.8 Redeploying later
```bash
docker buildx build --platform linux/amd64 -t $ECR/finance-api:v2 --push .
# App Runner console → your service → Deploy, pointed at :v2
```
Use a new tag each time rather than overwriting `:v1` — it makes rollback a
one-click change of image tag.

---

## Step 2 — Frontend

Your `frontend/src/api.ts` reads `VITE_API_URL` at **build time** (Vite inlines
it into the bundle). So the backend URL is baked into the build — changing it
means rebuilding, not just editing a setting.

### Option A — Amplify Hosting (recommended)

Git-connected, builds on push, CDN + HTTPS included, near-free at this scale.
Requires the repo on GitHub.

1. Push your work (you have a lot of uncommitted changes right now):
   ```bash
   cd ~/Developer/finance
   git status
   git add -A && git commit -m "prep for AWS deploy"
   git push
   ```
   Check `.gitignore` first — `node_modules`, `.venv`, and the client invoice
   PDFs sitting in the repo root should not go to GitHub.

2. **AWS Amplify** → **Create new app** → **GitHub** → authorize → pick the repo
   and branch.

3. Amplify auto-detects Vite but not the subdirectory. Set the build settings to:

   ```yaml
   version: 1
   applications:
     - appRoot: frontend
       frontend:
         phases:
           preBuild:
             commands:
               - npm ci
           build:
             commands:
               - npm run build
         artifacts:
           baseDirectory: dist
           files:
             - '**/*'
         cache:
           paths:
             - node_modules/**/*
   ```

4. **Environment variables** → add:

   | Name | Value |
   |------|-------|
   | `VITE_API_URL` | `https://<your-id>.ap-south-1.awsapprunner.com` — **no trailing slash** |

5. Save and deploy. You get `https://main.<app-id>.amplifyapp.com`.

Every `git push` to that branch rebuilds and redeploys automatically.

### Option B — S3 + CloudFront (manual, no GitHub needed)

```bash
cd ~/Developer/finance/frontend
VITE_API_URL=https://<your-id>.ap-south-1.awsapprunner.com npm run build

aws s3 mb s3://finance-frontend-<something-unique> --region ap-south-1
aws s3 sync dist/ s3://finance-frontend-<something-unique> --delete
```

Then **CloudFront** → **Create distribution**:
- Origin: your S3 bucket, with **Origin access control (OAC)** — leave the
  bucket private, let CloudFront read it. The console offers to update the
  bucket policy for you; accept.
- Default root object: `index.html`
- **Error pages**: map both **403** and **404** → `/index.html` with response
  code **200**. Without this, any path other than `/` returns an S3 error
  instead of your app.

Re-deploying means rebuilding, `s3 sync`, then a CloudFront invalidation:
```bash
aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"
```

---

## Step 3 — Lock down CORS

`backend/app/main.py:24` currently has `allow_origins=["*"]`, which means any
website can call your backend. Once the frontend URL is stable:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://main.<app-id>.amplifyapp.com"],
    allow_methods=["*"], allow_headers=["*"],
)
```

Rebuild and redeploy the backend (step 1.8).

---

## Step 4 — End-to-end check

1. Open the frontend URL, log in.
2. Company bar populates → `GET /api/config` is reaching App Runner.
3. Upload a **digital PDF** → invoice card appears.
4. Upload a **scanned JPEG** → exercises the Cloud Vision path.
5. Download a vouchers XLSX export → file downloads.
6. Import `GSTR-2A-sample.xlsx`, run reconcile.

If the UI loads but every API call fails, open DevTools → Network:
- Requests going to `<frontend-host>/api/...` → `VITE_API_URL` wasn't set at
  build time. Set it and **rebuild**.
- CORS errors → step 3, or the origin string has a typo/trailing slash.
- 502/503 from App Runner → check **Application logs** in the App Runner
  console. An arm64 image (step 1.4) shows up as an exec-format failure here.

---

## Before anyone else uses this

Two things in the current code that are fine for a demo and not fine in
production:

**The login is fake.** `frontend/src/auth.tsx:24` compares against
`admin`/`123456` in browser JavaScript, and the backend has no auth at all —
anyone with the App Runner URL can POST invoices to it directly. If this needs
to be real, the backend has to authenticate requests; **Amazon Cognito** plus a
FastAPI dependency that verifies the JWT is the AWS-native path.

**Config is process-global.** `COMPANY` in `backend/app/config.py:110` is one
shared mutable object. With `max-instances 2`, two users hitting different App
Runner instances see different company config, and one user's `POST /api/config`
changes the other's exports. Single-user demo: fine. Multi-user: config has to
move into the request (a header or body field) or into DynamoDB.

---

## Cost control cheatsheet

```bash
# Pause the backend when not in use (stops compute charges)
aws apprunner pause-service --service-arn <arn> --region ap-south-1
aws apprunner resume-service --service-arn <arn> --region ap-south-1

# Find the ARN
aws apprunner list-services --region ap-south-1

# ECR stores every old image tag and charges for it — prune when you have a few
aws ecr list-images --repository-name finance-api --region ap-south-1
aws ecr batch-delete-image --repository-name finance-api \
  --image-ids imageTag=v1 --region ap-south-1
```

Check **Billing → Cost Explorer** a few days in to see what you're actually
being charged for.

---

## Map

```text
Mac (arm64)
  └─ docker buildx --platform linux/amd64
        └─ ECR: <acct>.dkr.ecr.ap-south-1.amazonaws.com/finance-api:v1
              └─ App Runner  →  https://xxx.ap-south-1.awsapprunner.com
                                        ▲
                                        │ VITE_API_URL (baked in at build)
GitHub push                             │
  └─ Amplify Hosting  →  https://main.xxx.amplifyapp.com
```
