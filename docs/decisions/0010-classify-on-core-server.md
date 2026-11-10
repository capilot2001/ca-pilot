# ADR-0010: Classify stays on the core server, not the OCR service

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
Splitting OCR into its own service (ADR-0004) raises the question of *where the accounting
happens*. v1's `pipeline.process_file()` ends with `classify(inv)` — the natural seam between
reading and deciding.

## Decision
The **OCR service returns a reading only** (printed fields). The **core server runs
`classify`/`validate`** to derive nature of transaction, tax, ledgers, and the balanced journal.
Accounting never runs in the OCR service.

## Reasons
- Preserves **P4** ("reader reads, code decides") across the service boundary.
- Keeps the service **contract small and stable** (a reading), independent of accounting rules that
  change with GST law.
- Centralizes auditable accounting logic in one place the CA signs off on.
- The split point already exists in v1 at the `classify(inv)` line — a clean, low-risk cut.

## Alternatives considered
- **OCR service returns a fully-classified Invoice** — couples accounting rules into the extraction
  service, bloats the contract, and spreads auditable logic across services; rejected.

## Consequences
- The `shared/` contract is the *reading*, not the final Invoice.
- `classify`/`validate`/`masters` stay pure and server-side (no port around them, per P3).
- Changing GST rules touches only the server, never the OCR service.
