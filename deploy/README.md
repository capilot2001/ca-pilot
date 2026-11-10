# deploy — platform configuration (the only platform-aware part of the repo)

Per [ADR-0002](../docs/decisions/0002-deployment-independence.md), application code never knows its
platform; **all** platform knowledge lives here. Populated in module **A8**.

```
deploy/
├─ railway/     # server deploy config + SQLite volume (Railway)
├─ cloudrun/    # OCR service config (used when OCR is split out, post-migration)
├─ vercel/      # client deploy config (Part B)
└─ env/         # .env.example templates per service / environment
```

Moving a platform is a change here + env — never a code change.
