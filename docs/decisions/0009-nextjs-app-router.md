# ADR-0009: Next.js (App Router) for the frontend

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
The v1 frontend (React/Vite) is an API-reference UI, not a product. v2 needs a high-quality
dashboard, deployed on Vercel, targeting a full accounting UI over time.

## Decision
Build the new `client/` with **Next.js (App Router)** in TypeScript. Phase-0 UI is intentionally
narrow: an **Invoices page** listing invoices the user created, with an option to create one.
Likely stack: Tailwind + a component library (e.g. shadcn/ui) and a data-fetching layer (e.g.
TanStack Query) — confirmed when frontend work starts.

## Reasons
- First-class on Vercel; App Router gives modern routing, server components, and good DX.
- TypeScript matches the typed contracts in `shared/` and reduces drift with the API.
- Clean break from the v1 reference UI, which was never meant to be the product.

## Alternatives considered
- **Keep React/Vite** — rejected; it is an API harness, not a foundation for a product dashboard.
- **Plain SPA on another host** — loses Vercel/Next integration and SSR options.

## Consequences
- The v1 React frontend is replaced, not migrated.
- An **invoice-persistence** decision is required: the Invoices page implies persisting created
  invoices, which v1 does not do (tracked as an open question in architecture.md).
- Detailed UI scope (fields, create flow, async job UX from ADR-0005) is a frontend-phase decision.
