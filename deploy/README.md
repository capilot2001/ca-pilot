# deploy — platform configuration (the only platform-aware part of the repo)

Per [ADR-0002](../docs/decisions/0002-deployment-independence.md), application code never knows its
platform; **all** platform knowledge lives here.

```
deploy/
├─ railway/     # server (API + in-process OCR) + SQLite volume  [active]
├─ cloudrun/    # OCR service — placeholder until OCR is split out (post-migration)
├─ vercel/      # client deploy config (Part B)
└─ env/         # server.env.example — the env every platform fills in
```

The one deployable in Phase-0 is the **server** (`server/Dockerfile`, built from
the repo root because OCR runs in-process). It is defined once and configured
per platform through env; moving a platform is a change here + env, never a code
change. See each subfolder's README; `../docker-compose.yml` runs it locally.
