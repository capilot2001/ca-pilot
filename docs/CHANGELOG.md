# Changelog

Human-readable history of LedgerFlow v2. Code releases use semantic versioning; a release maps to
a phase (e.g. `v0.x` = Phase-0). ADRs and hypotheses reference the release they ship in.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased] — Phase-0 (in progress)

### Added (planning/documentation)
- Engineering documentation set: principles, architecture, decision records, hypotheses, phase-0
  plan, glossary. See [docs/README.md](README.md).
- Decision records ADR-0001 … ADR-0012 capturing the v2 architecture.
- Hypotheses H1 … H8, including the revised load model (20k invoices/day).

### Planned (Phase-0 implementation — not yet shipped)
- Migrate `v1-finance` → `v2-finance` with logic unchanged, restructured into
  `client / server / services / shared / deploy`.
- New Next.js (App Router) frontend with an Invoices page.
- Deployment: frontend on Vercel, backend on Railway, OCR service on Cloud Run.
- SQLite on a Railway volume; auth stub retained.

> Nothing is released yet. This section tracks Phase-0 work until it ships as `v0.1.0`.
