# Phase-0 — Implementation Plan

**Goal.** Migrate the existing v1 app into the v2 structure **with its logic unchanged** (P5),
restructured for deployment independence and future extensibility, plus a new high-quality
frontend with a first real screen (the Invoices page). Deploy as a dev/pilot across
Vercel + Railway + Cloud Run.

**This is a work order.** It closes when Phase-0 ships (`v0.1.0`). Durable rules are in
[../../principles.md](../../principles.md); the *why* for each choice is in the ADRs referenced per
item. See the per-phase lens in [summary.md](summary.md).

> Status legend: ☐ not started · ◐ in progress · ☑ done. Backend (A1–A9) shipped on
> `dev-backend`; migration-only — queue/persistence-growth/text-layer routing are deferred as
> new features. The frontend (§5, Part B) and the stray-asset reorg (§7) remain.

---

## In scope

### 1. Repo skeleton (ADR-0001) — A1
- ☑ Create `v2-finance/` layout: `client/ server/ services/ocr/ shared/ deploy/ docs/ assets/`.
- ☑ Root `docker-compose.yml` (run all services locally) + `Makefile` (up/test/lint/fmt).
- ☑ Root `README.md` pointing into `docs/`.

### 2. Migrate the backend logic unchanged (P5, ADR-0003/0010) — A2, A4, A5, A6
- ☑ Move accounting core → `server/` domain: `classify`, `validate`, `masters`, exporters,
  `models`. **No behaviour change.** (A2; verified byte-identical.)
- ☑ Introduce ports: `ClientRepository` (wrap existing `store.py`), `InvoiceExtractor`,
  `LLMInvoiceReader`; composition root `deps.py`; `settings.py` (pydantic-settings). (A5a/A5b)
- ☑ Reassemble FastAPI app under `server/app/api/` (routes, schemas); drop the mounted React
  bundle. (A6; 18-endpoint parity.)
- ☑ Tighten CORS from `*` to configured origins (via settings). (A6)

### 3. Extraction service (ADR-0004/0010/0011) — A5b, A7
- ☑ Move reading pipeline → `services/ocr/`: `ocr`, `llm_extract`, `parser`, pre-`classify` half of
  `pipeline`. (A3/A5b.) The standalone OCR-service HTTP `extract` endpoint lands at the split.
- ☑ Keep it a single job (rasterize → Vision → skew → Gemini → parse); **no accounting** inside
  (classify is server-side). (A5b)
- ◐ Wire `InProcessExtractor` behind the port; `OCR_MODE` selects. (A5b.) `HttpExtractor` is
  deferred to the OCR-service split (post-migration) — `OCR_MODE=http` raises until then.
- ☐ **text-layer-first routing** — deferred: it is a new feature, not part of the migration.

### 4. Shared contract (ADR-0001/0010) — A4
- ☑ Seed `shared/` from `models.py` — the **reading** contract both `server` and `services/ocr`
  import. One source of truth.

### 5. Frontend (ADR-0008/0009)
- ☐ New Next.js (App Router, TS) app in `client/`.
- ☐ Keep the **auth stub** (login shape preserved, isolated behind a seam).
- ☐ **Invoices page**: list invoices the user created + "create invoice" entry point.
- ☐ Resolve the **invoice-persistence** open question (does Phase-0 persist created invoices?).
- ☐ Wire upload → extract → review flow against the server API.

### 6. Deployment configs (ADR-0002/0006/0007) — A8
- ☑ `deploy/`: `railway/` (server + SQLite volume) and `env/` active; `vercel/` (client) and
  `cloudrun/` (OCR) are documented placeholders until Part B / the OCR split.
- ◐ `server/Dockerfile` with `$PORT` binding done (built from repo root for in-process OCR). The
  `services/ocr` Dockerfile lands with the OCR-service split.
- ☑ SQLite on a volume at `/data`; `LEDGERFLOW_DB` via settings.
- ☑ Google credentials: ADC on Cloud Run; mounted-key path documented for other platforms.

### 7. Reorganize stray assets/docs — done
- ☑ Sample invoices, xlsx/xml references, images → `assets/` (sample-invoices/
  with edge-cases/, tally-reference/, gstr2a/). Copied from v1 (v1 untouched).
- ☑ Deploy notes / cost estimates → `docs/reference/` (aws/gcp/deploy, cost
  estimate PDF + PPTX).

---

## Explicitly OUT of scope for Phase-0
- ❌ Real authentication / multi-tenant data isolation (ADR-0008) — later phase.
- ❌ The **queue + async workers** (ADR-0005) — design is locked, but Phase-0 may run sync/bounded
  for a small pilot. **The sync batch loop must not go to production.**
- ❌ Postgres (ADR-0007) — SQLite-on-volume for now.
- ❌ Full accounting dashboard beyond the Invoices page.
- ❌ Tally connector / GST-portal services.

## Done criteria (`v0.1.0`)
- ☑ v2 structure in place; backend logic produces **output identical to v1** on the sample invoices
  (verifies P5). (A9 parity gate: masters/vouchers XML + XLSX + reconcile byte-for-byte —
  `tests/parity/`.)
- ◐ OCR runs via the `InvoiceExtractor` port — in-process works now; its **own deployable** (HTTP)
  is the post-migration split.
- ☐ New Invoices page works end-to-end against the deployed stack (Vercel + Railway + Cloud Run).
- ☐ Moving any single platform is a `deploy/`+env change only (spot-check P1).
- ☐ `CHANGELOG.md` updated; this plan's boxes checked; `summary.md` outcome filled in.

## Known risks / watch items
- Invoice-persistence decision changes the data model — settle before building the Invoices page.
- Text-layer trust check: bad heuristics → garbage readings (H7).
- Verify the migrated logic truly matches v1 (diff outputs on samples), not just "looks right".
