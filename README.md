# LedgerFlow v2

AI-powered accounting automation for Indian Chartered Accountants. LedgerFlow turns invoices
(PDF/image) into **TallyPrime-ready** output: it reads each document with OCR + an LLM, applies
GST accounting logic in deterministic code, and exports Tally-importable XML/XLSX.

> **Status:** Phase-0 — design complete, implementation not started. This directory currently
> contains the engineering documentation; the code is migrated from `../v1-finance` in Phase-0.

---

## Start here

All the reasoning behind this codebase lives in **[docs/](docs/)**:

- **[docs/README.md](docs/README.md)** — documentation map + the versioning model
- **[docs/principles.md](docs/principles.md)** — the durable engineering rules (read first)
- **[docs/architecture.md](docs/architecture.md)** — system design, service split, capacity/cost
- **[docs/decisions/](docs/decisions/)** — Architecture Decision Records (the *why*)
- **[docs/hypotheses.md](docs/hypotheses.md)** — assumptions we're validating
- **[docs/phases/phase-0/](docs/phases/phase-0/implementation.md)** — what we're building now
- **[docs/glossary.md](docs/glossary.md)** — GST + architecture terms

---

## Core idea

> **The reader reads, the code decides.**

The AI/OCR layer only extracts what is *printed* on a document. All accounting judgement — nature
of transaction, GST tax, ledger selection, the balanced journal — is done by deterministic,
auditable code. This is what a CA can trust and sign off (see
[principles.md §P4](docs/principles.md)).

---

## Planned structure

The repo is a monorepo of independently-deployable units plus shared code and deployment config
(see [ADR-0001](docs/decisions/0001-monorepo-structure.md)):

```
v2-finance/
├─ client/        # Next.js frontend              → Vercel
├─ server/        # core accounting API (FastAPI)  → Railway
├─ services/
│   └─ ocr/       # OCR + LLM extraction service   → Cloud Run
│   # future: worker/, tally/, gst-portal/
├─ shared/        # shared Python contracts (the reading exchanged between server & ocr)
├─ deploy/        # platform configs ONLY (railway/ cloudrun/ vercel/ env/)
├─ docs/          # engineering documentation (you are here)
├─ assets/        # sample invoices, reference files
├─ docker-compose.yml   # local dev: run all services together
├─ Makefile
└─ README.md
```

Only `docs/` exists today; the rest is created during the Phase-0 migration
([plan](docs/phases/phase-0/implementation.md)).

---

## Architecture in one line

```
client (Vercel) → server (Railway): CRUD · classify · validate · exports
                        │ InvoiceExtractor port
                        ▼
                 services/ocr (Cloud Run): rasterize → Vision → skew → Gemini → reading
                        │
                 Google Cloud Vision + Gemini (Vertex AI)
```

The code is **deployment-platform-independent**: the container is the portability boundary and
config is the only thing that knows a platform. Moving hosts is a `deploy/` + env change, never a
code change ([§P1](docs/principles.md), [ADR-0002](docs/decisions/0002-deployment-independence.md)).

---

## Scale & cost (target, estimated)

100 CAs × ~200 invoices/day ≈ **20,000/day** (~440–600k/month). Google quotas give ~10× headroom;
the real design concerns are **cost** (~$1,300–2,500/month) and **per-tenant fairness** on the
shared worker pool. Details and sources in
[architecture.md §5](docs/architecture.md) and [hypotheses.md](docs/hypotheses.md).

---

## Getting started (once Phase-0 lands)

Local dev will run the whole topology via `docker-compose up` (client + server + OCR), wired by
env templates in `deploy/env/`. Setup steps will be documented here when the skeleton is created.
