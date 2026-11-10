# Phase-0 — Summary (lens into the log)

A pointer page: which durable decisions and hypotheses **belong to Phase-0**. It does not copy
them — the source of truth is [../../decisions/](../../decisions/) and
[../../hypotheses.md](../../hypotheses.md).

- **Release:** `v0.1.0` (planned) — see [../../CHANGELOG.md](../../CHANGELOG.md)
- **Status:** in progress (documentation done; implementation not started)
- **Last updated:** 2026-11-10

## Goals
Migrate v1 → v2 with logic unchanged, in a deployment-independent structure, and ship the first
real UI (Invoices page) as a dev/pilot across Vercel + Railway + Cloud Run. Full plan:
[implementation.md](implementation.md).

## Decisions introduced in Phase-0
ADR-0001 … ADR-0012 (the full founding set):

| # | Title |
|---|---|
| 0001 | Monorepo structure |
| 0002 | Deployment independence |
| 0003 | Ports & adapters + DI at real seams |
| 0004 | OCR as a separate service |
| 0005 | Queue-first extraction (design locked; build deferred) |
| 0006 | Dev topology (Vercel + Railway + Cloud Run) |
| 0007 | SQLite on a Railway volume |
| 0008 | Keep the auth stub |
| 0009 | Next.js App Router |
| 0010 | Classify stays on the core server |
| 0011 | Text-layer-first routing |
| 0012 | Documentation model |

## Hypotheses raised in Phase-0
H1 (load ~20k/day) · H2 (deadline bursts) · H3 (OCR is the heavy part) · H4 (SQLite-on-volume
holds) · H5 (Google cost ~$1.3–2.5k/mo) · H6 (sync breaks at scale) · H7 (digital-PDF share) ·
H8 (Vision quota headroom). See [../../hypotheses.md](../../hypotheses.md).

## Outcome
_To be filled when Phase-0 ships: what was validated/refuted, what changed, what carried into
Phase-1._
