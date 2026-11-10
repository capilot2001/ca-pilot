# Architecture

The current design of LedgerFlow v2. This reflects the **present** state of our decisions; the
*why* behind each choice is in [decisions/](decisions/), and the numbers rest on assumptions
tracked in [hypotheses.md](hypotheses.md).

> Principles referenced below (P1–P10) are defined in [principles.md](principles.md).

---

## 1. System at a glance

LedgerFlow turns invoices (PDF/image) into TallyPrime-ready output. The heavy "reading" is done
by Google's cloud (Vision OCR + Gemini); our services orchestrate and do the accounting.

Three deployable units plus managed infrastructure:

```
            ┌────────────┐      ┌──────────────────────┐
  CA  ───▶  │  client    │ ───▶ │  server              │  core API: CRUD, classify,
            │ (Next.js)  │      │  (FastAPI)           │  validate, exports, orchestration
            └────────────┘      └───────┬──────────────┘
                 Vercel                  │ InvoiceExtractor port
                                         │ (enqueue job)
                                   ┌─────▼─────┐
                                   │  queue    │  managed broker (Redis/Cloud Tasks/SQS)
                                   └─────┬─────┘
                                         │ consume (bounded, fair)
                            ┌────────────▼─────────────┐
                            │  services/ocr            │  rasterize → Vision → skew →
                            │  (FastAPI + worker)      │  Gemini → parse  ⇒ returns a *reading*
                            └────────────┬─────────────┘
                                 Cloud Run │
                        ┌──────────────────┴───────────────────┐
                        ▼                                       ▼
                 Google Cloud Vision                   Google Gemini (Vertex AI)
```

- **client** → Vercel. **server** → Railway. **services/ocr** → Cloud Run. **DB** → SQLite on a
  Railway volume (Phase-0). These are *current dev* placements; per **P1** the code does not
  depend on them.

---

## 2. Why the split: what is one server vs a separate service

The work is two different shapes, so it lives in two places.

**Core server (`server/`) — light, I/O-bound, low memory. Stays one service.**
- Client/invoice CRUD, config, auth (stub in Phase-0)
- `classify` / `validate` / `masters` — pure, cheap ("code decides", **P4**)
- Exports (XLSX/XML/PDF) — bounded
- Orchestration: accept uploads, enqueue jobs, serve results, run `classify` on returned readings

**OCR/extraction service (`services/ocr/`) — CPU + memory heavy, spiky. Separate, autoscaled.**
- 400-DPI PDF rasterization (PyMuPDF) — CPU + memory heavy
- Vision OCR call + skew estimation + row/column clustering + GSTIN repair — CPU
- Gemini reading call
- Parse → returns a **reading** (printed fields only; no accounting)

**Three reasons the split is justified (not premature — see P6):**
1. **Memory isolation** — a burst of multi-page 400-DPI jobs can spike RAM; that must not kill
   the API serving every other CA.
2. **Independent scaling** — OCR needs cores during deadline week and ~zero otherwise. A separate
   Cloud Run service autoscales on that curve (and scales to zero); the API server stays flat.
3. **Failure isolation** — an OCR crash/timeout on one bad scan does not take down CRUD/exports.

Keep the OCR pipeline as **one unit/one job** — do not split mid-pipeline, because the large
rasterized images feed both Vision and Gemini; splitting would push tens-of-MB images across the
network.

**What does NOT move:** `classify` stays on the core server (**ADR-0010**). The OCR service reads;
the server decides.

---

## 3. The seam that makes location a config choice

The server depends on an **`InvoiceExtractor` port**, not on "a remote OCR service". Which adapter
satisfies it is configuration (**P3**, **ADR-0004**):

| Adapter | Behaviour | Used for |
|---|---|---|
| `InProcessExtractor` | runs Vision+Gemini inside the server | local dev, tests, simplest deploys |
| `HttpExtractor` | POST to the OCR service, wait | current sync topology |
| `QueueExtractor` | enqueue job, result delivered async | target at scale |

Switching is an env change (`OCR_MODE`, `OCR_SERVICE_URL`), not a rewrite. `classify` and
everything downstream never move.

---

## 4. Request flows

**Sync (small volume / pilot):**
```
client ─upload─▶ server ─▶ InvoiceExtractor ─▶ OCR (Vision+Gemini) ─▶ reading
                 server: classify + validate ─▶ Invoice ─▶ client review ─▶ export
```
One request, waits. Breaks down for large batches (a 200-invoice batch ≈ 5–8 min > HTTP timeout).

**Async / queued (target at scale — ADR-0005):**
```
client ─upload─▶ server ─enqueue─▶ [QUEUE] ─▶ OCR worker ─▶ writes reading
                   │                                          │
                   └─ returns job_id ─▶ client polls /jobs/{id}◀┘ ─▶ classify ─▶ Invoice
```
The queue is the **backpressure + fairness** point (**P8**): worker concurrency is capped to stay
within Google quota, and scheduled per-tenant so one CA's 200-batch cannot starve others. The new
piece the queue forces is a **job-status endpoint** — a frontend change, not just backend.

---

## 5. Capacity & cost model

> **All figures are estimates to verify against live billing/quota.** They rest on H1–H8 in
> [hypotheses.md](hypotheses.md), notably the share of digital vs scanned invoices and real Gemini
> token sizes, which we chose to estimate rather than measure for now.

**Load (target):** 100 CAs × 200 invoices/day.

| Metric | Value |
|---|---|
| Per day | **20,000 invoices** |
| Per month | ~440k (22 working days) – 600k (30 days) |
| Avg rate (8h business window) | ~0.7 invoices/sec |
| Peak (~4× burst, deadline mornings) | ~2.8/sec; short spikes higher |

**Google quotas — headroom, not a wall:**

| Service | Limit | Our peak | Verdict |
|---|---|---|---|
| Cloud Vision | 1,800 req/min = **30/sec** (default) | ~2.8/sec | ~10× headroom; request increases if multi-page pushes up |
| Gemini 2.5 Flash | **Dynamic Shared Quota** (no per-project RPM) | — | auto-scales; best-effort. Use Provisioned Throughput for guaranteed peak capacity |

Vision batch in-processing caps (8,000 images / 10,000 pages in processing; 16 images/sync
request, 2,000/async) are generous at this scale.

**Cost (estimate):**

| Service | Rate | ~440k/month |
|---|---|---|
| Vision (text detection) | ~$1.50 / 1,000 units (first 1k free) | ~$660 (×pages if multi-page) |
| Gemini 2.5 Flash | input $0.30/1M, output $2.50/1M (Batch API ≈ half) | ~$600–1,600 (token-size dependent) |
| **Total Google** | | **~$1,300–2,500/month** |

≈ **$0.003–0.006 per invoice ≈ $13–26 per CA/month** in raw COGS — a direct input to SaaS pricing.
Gemini **output** tokens dominate (the $2.50 rate), so JSON size matters.

**Compute (local, our cost):** ~3 CPU-s/invoice (rasterize+skew+parse) ⇒ ~42 CPU-hours/month
total; a 1-hour spike of ~5k invoices needs ~4–5 cores (or a queue draining over a few hours). A
small autoscaling worker pool (a few cores, right-sized RAM) covers it. Memory is the real
constraint — a 400-DPI A4 page is tens of MB in RAM — so concurrency is **bounded** (P8).

**Cost/quota levers (P9):**
1. **Text-layer-first routing (ADR-0011):** prefer the PDF text layer before OCR. Digital PDFs
   skip Vision entirely *and* drop image tokens from Gemini — the single biggest saving, already
   half-built in v1's fallback reader.
2. **Batch API** for non-urgent jobs (≈ half price).
3. **Dedup** (`flag_duplicates` exists) and caching to avoid re-processing.

---

## 6. Where the v1 code maps (for the migration)

Grounding for Phase-0 (**P5**, logic unchanged). Current source lives under
`Codebase/v1-finance/backend/app/`:

| v1 file | Role | v2 home |
|---|---|---|
| `ocr.py`, `llm_extract.py`, `parser.py`, the pre-`classify` half of `pipeline.py` | reading pipeline | `services/ocr/` |
| `classify.py`, `validate.py`, `masters`, exporters, `models.py` | accounting core | `server/` (domain) |
| `store.py` (SQLite client repo) | persistence (already near-interface) | `server/` adapter behind `ClientRepository` port |
| `main.py` | FastAPI app + routes | `server/` api layer |
| `config.py` | constants + company config | split: domain constants vs `settings.py` |
| React/Vite `frontend/` | API-reference UI | replaced by new Next.js `client/` |

`models.py` (the shared Pydantic contract) is the natural seed of `shared/` — the reading
contract exchanged between `server` and `services/ocr`.

---

## 7. Open questions (tracked, not yet decided)
- Invoice **persistence**: v1 is stateless (only the client list persists). The new Invoices page
  implies persisting created invoices — a Phase-0 frontend decision not yet made.
- Exact queue technology (Redis+RQ vs Cloud Tasks vs SQS) — deferred until we implement the async
  path; the `InvoiceExtractor` port keeps it swappable.
