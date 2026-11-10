# ADR-0007: SQLite on a Railway volume for Phase-0

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
v1 persists only the client list, in SQLite (`store.py`, `LEDGERFLOW_DB`). Phase-0 migrates logic
unchanged (**P5**). Cloud Run / Railway containers have ephemeral filesystems — a plain SQLite file
is lost on redeploy without durable storage. We also expect persistence to grow (e.g. created
invoices).

## Decision
Keep **SQLite**, stored on a **Railway persistent volume**, for Phase-0. Access stays behind the
`ClientRepository` port so the engine can change later without touching callers.

## Reasons
- True "migrate unchanged" — no logic/schema rewrite in Phase-0.
- A volume gives durability across redeploys; the server is the single writer (SQLite is an
  embedded file, not a networked service).
- The port means a move to Postgres later = a new adapter + `DATABASE_URL`, not a rewrite (**P3**).

## Alternatives considered
- **Postgres now** — a real networked DB, better for concurrency/scale, but a migration Phase-0
  explicitly defers; revisit when multi-writer concurrency or analytics demand it (H4).
- **SQLite as a separate "service"** — a category error: SQLite is an embedded file, not a server;
  rejected.

## Consequences
- Single-writer model is fine at Phase-0 scale; concurrency ceilings are a known Postgres trigger.
- The volume must be backed up; it is now stateful infrastructure (P7 state lives in the datastore).
- H4 tracks whether SQLite-on-volume holds for the target user count.
