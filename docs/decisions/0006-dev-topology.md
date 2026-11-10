# ADR-0006: Dev topology — Vercel + Railway + Cloud Run

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
We need a concrete dev/pilot deployment now. Production may later consolidate on Railway or move to
AWS. Per **P1**, this placement must not leak into the code.

## Decision
For development/pilot:
- **client** (Next.js) → **Vercel**
- **server** (FastAPI core API) → **Railway**
- **services/ocr** → **Google Cloud Run**
- **DB** → SQLite on a **Railway volume** (ADR-0007)

## Reasons
- Vercel is ideal for Next.js; Railway runs containers well (we have prior experience) and offers
  volumes + private networking; Cloud Run fits OCR (autoscale, scale-to-zero, automatic ADC for
  Google APIs).
- Putting OCR on GCP keeps Google credentials ambient (ADC) and off Railway.
- The Python OCR backend is a poor fit for Vercel serverless (size/timeout/no persistent FS), which
  is why backend + OCR are not on Vercel.

## Alternatives considered
- **Everything on Vercel** — rejected; serverless limits break the OCR workload.
- **Everything on Railway now** — viable, but Cloud Run's scale-to-zero + ambient ADC are a better
  fit for the spiky, Google-dependent OCR service during dev. Remains a likely prod option.
- **Everything on AWS now** — heavier setup than needed for a pilot; a documented prod option.

## Consequences
- Three platforms to configure (all via `deploy/`), each with its own env/secrets.
- Cross-service calls (server → OCR) go over the network; secured and configured via env.
- Switching any of these later is a `deploy/` + env change (P1), not a code change.
