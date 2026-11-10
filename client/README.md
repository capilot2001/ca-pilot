# client — LedgerFlow v2 frontend

**Not built yet.** The frontend is created in **Part B** of the migration, *after* the backend is
migrated and verified (parity gate A9).

- Stack: Next.js (App Router) + TypeScript — see [ADR-0009](../docs/decisions/0009-nextjs-app-router.md).
- Built fresh from scratch; the v1 React/Vite app is used **only as an API reference**, not migrated.
- Migration scope mirrors v1's existing flow (upload → extract → review/edit → export). Persisted
  invoices and the Invoices list are a later feature, not part of the migration.

This folder is a placeholder so the repo structure is complete.
