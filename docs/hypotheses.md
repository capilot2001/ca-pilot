# Hypotheses

Assumptions we are **betting on but have not proven**. Distinct from decisions (ADRs): a decision
is a choice; a hypothesis is a belief with a validation plan. Append-only — a refuted hypothesis
stays, marked `Refuted`, with what we learned.

**Status:** Open · Confirmed · Refuted · Partially confirmed.

> Many cost/scale numbers below are **estimates we chose not to measure yet** (we have v1 sample
> invoices to measure against when we want to tighten them).

---

### H1 — Load is ~20,000 invoices/day (100 CAs × 200/day)
- **Phase raised:** phase-0 · **Status:** Open
- **Belief.** Target scale is 100 CAs each processing ~200 invoices/day — delivered as one batch of
  200 or several smaller batches through the day — i.e. ~440–600k/month.
- **Why.** User's revised estimate of the client base and per-CA throughput.
- **Validate.** Measure actual per-CA daily volume once a pilot cohort is live; watch the
  distribution (bursts vs steady).
- **Falsified if.** Real volume is materially lower/higher, or far spikier than a ~4× peak factor.
- **Supersedes earlier estimate:** an initial 20–50k/month figure (≈10–20× lower) is withdrawn.

### H2 — Load is bursty around GST filing deadlines
- **Phase raised:** phase-0 · **Status:** Open
- **Belief.** Volume concentrates into a few working days before GSTR-1 (~11th) and GSTR-3B (~20th),
  in business hours; peak ≈ 4× the average rate.
- **Why.** How CA filing work is structured.
- **Validate.** Plot volume by day-of-month and hour once live.
- **Falsified if.** Load is roughly uniform, or peaks far exceed 4×.

### H3 — Local heavy cost is rasterization + skew; splitting OCR is justified
- **Phase raised:** phase-0 · **Status:** Open
- **Belief.** The CPU/memory-heavy local work is 400-DPI rasterization and skew estimation (~3
  CPU-s/invoice), spiky enough that isolating OCR into its own autoscaled service is warranted.
- **Why.** Code review of v1 `ocr.py`/`pipeline.py`.
- **Validate.** Profile CPU/RAM per invoice under load; confirm memory spikes justify isolation.
- **Falsified if.** Per-invoice compute is negligible and an in-process model holds at target scale
  (would weaken ADR-0004's "separate now" stance — the port keeps that reversible).

### H4 — SQLite on a volume holds for Phase-0
- **Phase raised:** phase-0 · **Status:** Open
- **Belief.** Single-writer SQLite on a Railway volume is sufficient for Phase-0's persistence
  (client list, and possibly created invoices) at the target user count.
- **Why.** Migrate-unchanged (ADR-0007); write volume is modest and single-writer.
- **Validate.** Load-test writes/concurrency; watch for lock contention.
- **Falsified if.** Concurrent writes or analytics needs cause contention → triggers Postgres
  (adapter swap behind `ClientRepository`).

### H5 — Google API cost lands ~$1,300–2,500/month at 440k
- **Phase raised:** phase-0 · **Status:** Open (estimate)
- **Belief.** Vision (~$660) + Gemini 2.5 Flash (~$600–1,600) ≈ $1,300–2,500/month at ~440k
  invoices; ≈ $0.003–0.006/invoice ≈ $13–26 per CA/month COGS.
- **Why.** Live Google pricing × estimated token/page counts (Gemini **output** tokens dominate).
- **Validate.** Run the v1 sample invoices through the pipeline and read actual token counts +
  billing.
- **Falsified if.** Real token sizes / multi-page rates move the total outside the range.

### H6 — Synchronous batch processing breaks at this scale
- **Phase raised:** phase-0 · **Status:** Open (strongly expected)
- **Belief.** A 200-invoice batch processed synchronously (~5–8 min) exceeds HTTP/Cloud Run
  timeouts, forcing an async/queued design (ADR-0005).
- **Why.** Two sequential cloud calls × 200, serial.
- **Validate.** Time a real 200-batch end-to-end against platform timeout limits.
- **Falsified if.** Platform timeouts are generous enough and bounded concurrency alone keeps
  batches under them (unlikely at 200).

### H7 — A meaningful share of invoices are digital PDFs (text-layer-first pays off)
- **Phase raised:** phase-0 · **Status:** Open
- **Belief.** Enough real invoices carry a reliable text layer that text-layer-first routing
  (ADR-0011) materially cuts Vision cost + Gemini image tokens.
- **Why.** Many B2B invoices are system-generated digital PDFs.
- **Validate.** Classify the v1 sample set (and later real uploads) into digital vs scanned; measure
  text-layer reliability.
- **Falsified if.** Most invoices are scans/photos with no usable text layer → smaller savings.

### H8 — Vision quota (1,800/min) is not a bottleneck at target scale
- **Phase raised:** phase-0 · **Status:** Open (supported by current docs)
- **Belief.** Default Vision quota of 30 req/sec vs our ~2.8/sec peak leaves ~10× headroom; Gemini
  DSQ auto-scales. Quotas are not the constraint — cost and fairness are.
- **Why.** Google's published quota docs (2026-11-10).
- **Validate.** Monitor 429 rates under real bursts, especially with multi-page invoices.
- **Falsified if.** Multi-page expansion or tighter-than-documented limits cause throttling →
  request increases / Provisioned Throughput.
