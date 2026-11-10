# ADR-0004: OCR as a separate service behind an InvoiceExtractor port

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
Per-invoice extraction (400-DPI rasterization + Vision OCR + skew/clustering + Gemini) is the
heavy, memory-hungry, spiky part of the system. It must scale and fail independently of the core
API, and it carries the Google-credential dependency.

## Decision
Make OCR/extraction a **separately-deployable service** (`services/ocr/`) that the core server
reaches through an **`InvoiceExtractor` port**. The port has interchangeable adapters selected by
config:
- `InProcessExtractor` — runs in the server (local dev, tests, simplest deploys)
- `HttpExtractor` — calls the OCR service synchronously (current)
- `QueueExtractor` — enqueues a job, async result (target at scale; see ADR-0005)

The OCR service exposes an `extract` operation taking file bytes and returning a **reading**
(printed fields only — no accounting, per **P4**/ADR-0010).

## Reasons
- **Memory/failure isolation** and **independent autoscaling** (OCR spikes at GST deadlines, idle
  otherwise) — a separate Cloud Run service sizes/bills to that curve.
- Keeps the Google-credential-heavy code on GCP (ADC automatic on Cloud Run); the Railway server
  stays Google-free.
- The port means *location is a config choice*: in-process vs HTTP vs queued, no code rewrite
  (**P1/P6**).

## Alternatives considered
- **Keep OCR in-process in the monolith** — simplest, but couples memory/failures/scaling to the
  API and strands Google creds on Railway; rejected for production, retained as the
  `InProcessExtractor` for dev.
- **Split the pipeline across services** — rejected; the large rasterized images feed both Vision
  and Gemini, so mid-pipeline splits push big payloads over the network.

## Consequences
- A reading contract must live in `shared/` so both sides agree on the payload.
- Two deploy targets instead of one; justified by the isolation/scaling benefits.
- Phase-0 may run in-process and still be "correct"; the service boundary exists in code from day
  one so the switch is config-only.
