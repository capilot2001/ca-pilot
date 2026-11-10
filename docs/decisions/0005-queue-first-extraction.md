# ADR-0005: Queue-first async extraction with per-tenant fairness + quota backpressure

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
Revised load is **100 CAs × 200 invoices/day = 20,000/day** (~440–600k/month) — ~10–20× the earlier
estimate (see H1). A single 200-invoice batch processed synchronously takes ~5–8 min, exceeding
normal HTTP/Cloud Run timeouts. One shared worker pool and one shared Google quota serve all 100
CAs.

## Decision
The target extraction path is **asynchronous via a managed queue**:
- The core server enqueues a job and returns a `job_id`; the client polls a **job-status endpoint**
  (or is pushed via websocket/webhook).
- OCR **workers** consume the queue (the OCR service in consumer mode).
- The queue is the **backpressure** point: worker concurrency is capped to stay within Google
  quota (Vision 30/sec; Gemini DSQ best-effort).
- The queue enforces **per-tenant fairness** (per-CA concurrency cap / fair round-robin) so one
  CA's large batch cannot starve others (**P8**).

Queue technology (Redis+RQ/Celery vs Cloud Tasks vs SQS) is deferred; the `InvoiceExtractor` port
(`QueueExtractor` adapter) keeps it swappable.

## Reasons
- At 20k/day the sync model breaks on timeouts regardless of raw throughput.
- Quotas give ~10× headroom, so the real risks are **concurrency**, **fairness**, and **cost** —
  all of which a queue addresses (rate-limit, schedule, retry).
- Keeps the existing retry/backoff + circuit breaker (already in `llm_extract`) meaningful under
  429s.

## Alternatives considered
- **Synchronous bounded concurrency only** — a quick win (overlaps network waits, ~6 min → ~1 min
  for a 50-batch) but still risks timeouts and gives no cross-tenant fairness; kept as a *pilot*
  option, not the production design.
- **No fairness (FIFO)** — simplest queue, but one 200-batch delays every other CA; rejected (P8).

## Consequences
- A new **job-status endpoint** and async UX on the frontend (upload → job_id → poll → result).
- Extraction *logic* is unchanged (**P5**); only orchestration changes.
- Phase-0 may ship a small pilot without the full queue, but **the sync batch loop must not go to
  production**.
