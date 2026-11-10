# LedgerFlow v2 — Engineering Documentation

This folder is the source of truth for **how we build LedgerFlow v2 and why**. It exists so
that anyone joining later understands the rules we set, the decisions we made, the bets we are
taking, and what each phase actually ships — without having to reconstruct it from the code or
from chat history.

> Scope: these docs govern the **`v2-finance` codebase**. Product/proposal material lives in the
> repository-root `Docs/` folder, not here.

---

## How to read this (reading order)

1. **[principles.md](principles.md)** — the durable rules. Start here. These apply across every
   phase and change rarely.
2. **[architecture.md](architecture.md)** — the current system: service topology, the service
   split, request flows, and the capacity/cost model.
3. **[decisions/](decisions/)** — the Architecture Decision Records (ADRs): every significant
   choice, with its context, reasoning, and alternatives.
4. **[hypotheses.md](hypotheses.md)** — the assumptions we are betting on and how we will
   validate them.
5. **[phases/](phases/)** — what each phase implements. Current: **[phase-0](phases/phase-0/implementation.md)**.
6. **[glossary.md](glossary.md)** — GST/accounting and architecture terms. Keep this open if the
   vocabulary is new.
7. **[CHANGELOG.md](CHANGELOG.md)** — human-readable release history.

---

## The versioning model (important)

We do **not** fork this knowledge base per version. Copying everything into `v0/`, `v1/`, `v2/`
folders fragments the decision history and leaves stale copies. Instead, three layers each age
differently:

| Layer | Docs | How it versions |
|---|---|---|
| **Living / durable** | `principles.md`, `architecture.md`, `glossary.md` | One copy, always current. History lives in git + the ADR that changed it. |
| **Append-only log** | `decisions/` (ADRs), `hypotheses.md` | One continuous log. Each entry is **stamped** with the phase it was made in and a status. Superseded, never deleted or forked. |
| **Per-version work order** | `phases/phase-N/` | Genuinely one folder per phase. Closes when the phase ships. |

**Why:** a decision made in Phase-0 often still governs Phase-3. Folderizing it would falsely
imply it expired. So decisions and hypotheses live in one log and carry metadata; only the *work
order* is truly per-version.

### Where "what did we decide in version X" lives
Each phase has a **`summary.md`** that *points at* (does not copy) the ADRs and hypotheses that
belong to it:

> Phase-1 — Decisions introduced: ADR 0013–0015 · Hypotheses raised: H9–H10 · Outcome: …

The single log stays the source of truth; the phase summary is the lens onto it.

### Rules for editing these docs
- **Principles** change rarely, and a change is itself recorded as an ADR.
- **ADRs are immutable once Accepted.** To change a decision, write a *new* ADR that
  `Supersedes:` the old one. Never edit an accepted ADR's decision away.
- **Hypotheses are never deleted.** A refuted hypothesis stays, marked `Refuted`, with what we
  learned.
- **Architecture.md reflects the current state.** Past states live in git history and the ADRs.
- Tie docs to code releases: ADRs/hypotheses reference the release (see `CHANGELOG.md`).

---

## Status

- **Current phase:** Phase-0 (migration + first real UI). See [phases/phase-0](phases/phase-0/implementation.md).
- **Last updated:** 2026-11-10
