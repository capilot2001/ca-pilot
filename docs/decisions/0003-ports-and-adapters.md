# ADR-0003: Hexagonal ports & adapters + dependency injection at real seams

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
We want to swap the database or the LLM provider later by changing a dependency, not by rewriting
logic across files — but without over-engineering for the current scale (**P6**).

## Decision
Adopt pragmatic **Hexagonal (Ports & Adapters)** with dependency injection, applying ports
**only at real seams**:

- **Ports (interfaces, `typing.Protocol`)** at: persistence (`ClientRepository`), LLM
  (`LLMInvoiceReader`), OCR/extraction (`InvoiceExtractor`), and future external systems.
- **Adapters** implement them: `SqliteClientRepo`, `GeminiReader`/`ClaudeReader`/`OpenAIReader`
  (chosen by `LLM_PROVIDER` via a factory), `HttpExtractor`/`InProcessExtractor`, etc.
- **Composition root** (`deps.py`) reads settings and wires which adapter satisfies each port.
- **DI mechanism** = FastAPI `Depends` — no separate DI framework.
- **No ports around pure functions** (`classify`, `validate`, `masters`) — they have one
  implementation and no external boundary (**P3**).

Proposed `server/app/` layout: `domain/ · ports/ · adapters/ · services/ · api/ · settings.py · deps.py`.

## Reasons
- Makes the expensive, swappable things swappable (DB, LLM, OCR) via config + factory.
- `typing.Protocol` over ABCs: structural typing, no inheritance coupling, less boilerplate.
- Avoids indirection where there is no second implementation — extensible *without* bloat.

## Alternatives considered
- **Ports everywhere (including pure logic)** — textbook-pure but pure overhead here; rejected (P3).
- **No abstraction, direct calls** — simplest now, but a DB/LLM swap becomes a cross-file rewrite;
  rejected given we expect those swaps.
- **A DI framework** — unnecessary; FastAPI `Depends` already injects.

## Consequences
- A DB or LLM change = a new adapter + a settings value, not edits across the codebase.
- `store.py` is already near-interface and maps cleanly to `ClientRepository`.
- Contributors must know the rule for *when* a port is warranted (the seam test), documented in P3.
