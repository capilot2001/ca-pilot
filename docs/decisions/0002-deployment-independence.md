# ADR-0002: Deployment independence via per-service Dockerfiles + config

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
Dev topology is Vercel + Railway + Cloud Run; production may be all-Railway or AWS. We must be
able to move platforms without rewriting the application. This is the central constraint (**P1**).

## Decision
Make the **container the portability boundary** and **config the only platform-aware thing**:
1. Each service ships its own Dockerfile and runs identically on any platform.
2. All platform/secret values come from env, loaded via one typed settings module per service
   (**P2**): `DATABASE_URL`, `OCR_MODE`, `OCR_SERVICE_URL`, `LLM_PROVIDER`, `PORT`, `CORS_ORIGINS`,
   credentials, etc. No `if cloud_run:` branches.
3. `deploy/` holds per-platform run-config (railway.toml, Cloud Run service.yaml, vercel.json) and
   env templates — the *only* place platform knowledge lives.
4. `docker-compose.yml` runs the whole topology locally, mirroring prod wiring.

## Reasons
- Moving platforms becomes a `deploy/` + env change, never a code change.
- 12-factor config keeps secrets out of the repo and makes environments reproducible.
- The existing v1 Dockerfile already binds `$PORT` — the pattern is proven.

## Alternatives considered
- **Platform-specific code paths / SDKs** — fastest short-term, but welds us to one vendor;
  rejected, it violates P1.
- **A single root Dockerfile** — cannot build multiple services (see ADR-0001).

## Consequences
- Discipline required: anything environment-specific must go through settings, never literals.
- Credentials differ by platform (ADC is automatic on Cloud Run; a key file is needed elsewhere) —
  handled via config/secrets, not code.
- CI builds one image per service.
