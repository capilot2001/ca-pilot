# ADR-0012: Documentation model — living docs + append-only log + per-phase work order

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
The project will span multiple versions/phases, each adding features with their own decisions and
hypotheses. We need versioned documentation that future contributors can trust, without
fragmenting history into stale per-version copies.

## Decision
Three layers, each versioned differently:
- **Living/durable** (`principles.md`, `architecture.md`, `glossary.md`) — one current copy;
  history via git + the ADR that changed it.
- **Append-only log** (`decisions/` ADRs, `hypotheses.md`) — one continuous log; each entry
  **stamped** with its phase + status; superseded, never deleted or forked.
- **Per-version work order** (`phases/phase-N/`) — genuinely one folder per phase.

Each phase has a `summary.md` that *points at* (does not copy) the ADRs/hypotheses belonging to it.
Code uses semantic versioning mapped to phases; ADRs/hypotheses reference the release
(`CHANGELOG.md`).

## Reasons
- A decision made in one phase often still governs later ones — folderizing it per version would
  falsely imply it expired.
- One supersession chain + status filter answers "what governs us now" without stale duplicates.
- The per-phase summary still gives the "what did we decide in version X" view, by reference.

## Alternatives considered
- **Hard `phase-N/` folders for decisions/hypotheses** — simpler to browse, but fragments the
  supersession chain and duplicates principles; rejected.
- **One giant `decisions.md`** — does not scale; ADRs deserve individual files with
  alternatives/consequences.

## Consequences
- Contributors must follow the ADR discipline: supersede, don't edit; never delete a hypothesis.
- A small amount of indirection (phase summaries point into the log) in exchange for a single
  source of truth.
