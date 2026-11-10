# ADR-0008: Keep the auth stub for Phase-0

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
v1 has a hardcoded auth stub (`admin` / `123456`, stored in localStorage). Real multi-tenant auth
is a significant build. Phase-0's goal is migration + the first real UI, not authn/authz.

## Decision
Retain the **auth stub** in Phase-0. Do not build real authentication yet, but isolate it behind a
clear seam so it can be replaced without touching feature code.

## Reasons
- Keeps Phase-0 focused on migration + the Invoices UI.
- Real auth (multi-tenant, per-CA isolation, sessions) is its own phase and interacts with the
  per-tenant fairness model (ADR-0005) — better designed together, later.

## Alternatives considered
- **Build real auth now** — scope creep for Phase-0; deferred.
- **No auth at all** — rejected; the stub preserves the login shape so the later swap is contained.

## Consequences
- **Not production-ready security.** Phase-0 is pilot/demo; real tenancy is a prerequisite before
  onboarding real CAs with real data.
- Multi-tenancy (per-CA data isolation) must land with real auth; the shared-pool fairness design
  already anticipates tenants.
