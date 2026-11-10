# Architecture Decision Records (ADRs)

One append-only log of every significant decision. ADRs are **immutable once Accepted** — to
change a decision, write a *new* ADR that `Supersedes:` the old one. This preserves the reasoning
chain across versions (see the versioning model in [../README.md](../README.md)).

New ADR: copy [template.md](template.md), take the next number, fill it in, add a row below.

## Index

| # | Title | Phase | Status | Supersedes |
|---|---|---|---|---|
| [0001](0001-monorepo-structure.md) | Monorepo structure (client/server/services/shared/deploy) | phase-0 | Accepted | — |
| [0002](0002-deployment-independence.md) | Deployment independence via per-service Dockerfiles + config | phase-0 | Accepted | — |
| [0003](0003-ports-and-adapters.md) | Hexagonal ports & adapters + DI at real seams | phase-0 | Accepted | — |
| [0004](0004-ocr-as-separate-service.md) | OCR as a separate service behind an InvoiceExtractor port | phase-0 | Accepted | — |
| [0005](0005-queue-first-extraction.md) | Queue-first async extraction with fairness + quota backpressure | phase-0 | Accepted | — |
| [0006](0006-dev-topology.md) | Dev topology: Vercel + Railway + Cloud Run | phase-0 | Accepted | — |
| [0007](0007-sqlite-on-volume.md) | SQLite on a Railway volume for Phase-0 | phase-0 | Accepted | — |
| [0008](0008-auth-stub.md) | Keep the auth stub for Phase-0 | phase-0 | Accepted | — |
| [0009](0009-nextjs-app-router.md) | Next.js App Router for the frontend | phase-0 | Accepted | — |
| [0010](0010-classify-on-core-server.md) | Classify stays on the core server, not the OCR service | phase-0 | Accepted | — |
| [0011](0011-text-layer-first-routing.md) | Text-layer-first routing (cost/quota lever) | phase-0 | Accepted | — |
| [0012](0012-documentation-model.md) | Documentation model: living + append-only log + per-phase work order | phase-0 | Accepted | — |

## Status values
- **Proposed** — under discussion.
- **Accepted** — in force. Do not edit the decision; supersede it.
- **Superseded by NNNN** — replaced; kept for history.
- **Deprecated** — no longer applies, not replaced.
