# Glossary

Terms used across LedgerFlow v2 — Indian GST/accounting and architecture. Keep this open if the
vocabulary is new.

## GST / accounting (domain)

| Term | Meaning |
|---|---|
| **CA** | Chartered Accountant — our primary user. Manages books/filings for multiple businesses. |
| **GSTIN** | Goods & Services Tax Identification Number — 15-char ID of a registered business. Has a checksum we validate. |
| **HSN / SAC** | Harmonized System of Nomenclature (goods) / Service Accounting Code (services) — classification codes that drive tax rates. |
| **CGST / SGST / IGST** | Central / State / Integrated GST. Intra-state supply → CGST+SGST; inter-state → IGST. |
| **Place of supply** | The state where a supply is deemed to occur — decides intra- vs inter-state, hence which taxes apply. |
| **ITC** | Input Tax Credit — tax paid on purchases that offsets tax owed on sales. |
| **GSTR-1** | Monthly return of outward supplies (sales). Filed around the 11th. |
| **GSTR-2A / 2B** | Auto-drafted statements of inward supplies (purchases) from suppliers' filings; used for reconciliation. |
| **GSTR-3B** | Monthly summary return + tax payment. Filed around the 20th. |
| **Reconciliation** | Matching our purchase records against GSTR-2A/2B to find mismatches/missing ITC. |
| **Voucher** | An accounting entry in Tally. *Item* vouchers carry stock lines; *accounting* vouchers are money-only. |
| **Masters** | Reference records in Tally (ledgers, stock items, groups) that vouchers reference. |
| **TallyPrime** | The desktop accounting software CAs use. We produce Tally-importable XML/XLSX. |
| **Journal** | The double-entry record (debits = credits). Balanced in code via a Round Off line. |
| **Nature of transaction** | GST classification of a supply (e.g. intra-state taxable sale) that drives tax + ledger selection. |

## Architecture

| Term | Meaning |
|---|---|
| **Port** | An interface (Python `Protocol`) at a real seam — e.g. `ClientRepository`, `InvoiceExtractor`, `LLMInvoiceReader`. |
| **Adapter** | A concrete implementation of a port — e.g. `SqliteClientRepo`, `HttpExtractor`, `GeminiReader`. |
| **Composition root** | The one place (`deps.py`) that reads config and wires which adapter satisfies each port. |
| **DI (dependency injection)** | Giving a component its dependencies from outside rather than constructing them inside. We use FastAPI `Depends`. |
| **Reading** | The structured, *pre-accounting* data the OCR service extracts from a document (printed fields only). Input to `classify`. |
| **Core server / API backend** | The main FastAPI service: CRUD, classify/validate, exports, orchestration. Light, I/O-bound. |
| **OCR service** | The separately-deployable extraction service: rasterize → Vision → skew → Gemini → parse. Heavy, CPU/memory-bound. |
| **Broker / queue** | Managed infrastructure holding jobs (e.g. Redis+RQ/Celery, Cloud Tasks, SQS). Not code we write. |
| **Worker** | A process that pulls jobs off the queue and runs them. The OCR service in "consumer" mode. |
| **Producer** | Whatever enqueues a job — here, the core server. |
| **Backpressure** | Limiting intake/throughput so a downstream (workers, Google quota) is not overwhelmed. |
| **Per-tenant fairness** | Scheduling so each CA gets a fair share of the shared pool/quota; one big batch can't starve others. |
| **DSQ** | Dynamic Shared Quota — Vertex AI's pooled, auto-scaling capacity model for Gemini (no per-project RPM to manage). |
| **ADC** | Application Default Credentials — Google's ambient auth; automatic on Cloud Run, needs a key file elsewhere. |
| **ADR** | Architecture Decision Record — one documented decision in [decisions/](decisions/). |
