# ADR-0001: Monorepo structure (client / server / services / shared / deploy)

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
v2 has multiple deployable units (a frontend, a core API, a heavy OCR service) plus data they
share. We need a repo layout that is readable, keeps deployment knowledge in one place, and scales
to more services (worker, Tally connector, GST portal) later. The initial suggestion was
`client / server / services / deploy / README` with a root Dockerfile.

## Decision
A single monorepo under `Codebase/v2-finance/`:

```
v2-finance/
├─ client/        # Next.js frontend              → Vercel
├─ server/        # core accounting API (FastAPI)  → Railway   (+ its own Dockerfile)
├─ services/
│   └─ ocr/       # OCR + LLM extraction service   → Cloud Run (+ its own Dockerfile)
│   # future: worker/, tally/, gst-portal/
├─ shared/        # shared Python contracts (domain models)
├─ deploy/        # platform configs ONLY (railway/ cloudrun/ vercel/ env/)
├─ docs/
├─ assets/
├─ docker-compose.yml   # local dev: all services wired like prod
├─ Makefile
└─ README.md
```

## Reasons
- `server` = the one primary API; `services/` = satellite microservices. Clear rule, room to grow.
- `shared/` holds the data contract exchanged between `server` and `services/ocr`, so they cannot
  drift (one source of truth).
- `deploy/` isolates platform knowledge (supports **P1**).
- Dockerfiles live **next to each service** (self-contained, buildable); a single root Dockerfile
  cannot build a multi-service repo.

## Alternatives considered
- **User's original `client/server/services/deploy` + root Dockerfile** — kept the good names but
  (a) lacked a home for shared contracts and (b) a root Dockerfile does not fit multiple services.
  Adopted with those two corrections.
- **`apps/` + `packages/` (Turborepo/Nx convention)** — more formal, better with monorepo tooling,
  but heavier and less readable for our ~3 services now. Revisit past ~5 services.

## Consequences
- Each service builds its own image; `docker-compose.yml` runs them together locally.
- `shared/` must be included in each service's Docker build context (build context = repo root, or
  install it as a local package) — a known, small packaging cost.
- Adding a service = a new folder under `services/` + a `deploy/` entry; no churn elsewhere.
