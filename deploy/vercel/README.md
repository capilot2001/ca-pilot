# Vercel — the client (Part B)

Vercel hosts the new Next.js client (`client/`), which is built from scratch in
**Part B** of Phase-0. There is nothing to deploy here yet — the client does not
exist until then.

When it does:
- **Root directory:** `client/`
- **Framework:** Next.js (App Router) — Vercel detects it; no build override.
- **Variable:** `NEXT_PUBLIC_API_URL` = the server's URL (the Railway service),
  which must also be listed in the server's `CORS_ORIGINS`.

The client is stateless and talks only to the server API, so it carries no
secrets beyond that public base URL.
