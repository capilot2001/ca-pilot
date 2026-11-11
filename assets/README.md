# assets — sample invoices & Tally reference files

Reference material for development and testing, copied from the v1 project (v1
is left untouched). Not imported by the running code.

## `sample-invoices/`
Real sample bills for exercising the OCR + reading pipeline (extraction needs
Google Cloud credentials — see `../deploy/env/server.env.example`).
- `*.pdf`, `first.jpg`, `second.jpg` — assorted purchase / sales invoices.
- `edge-cases/` — invoices that deliberately trip validations (invalid GSTIN,
  missing registration / place-of-supply) to exercise the exception paths.

## `gstr2a/`
- `GSTR-2A-sample.xlsx` — a GSTR-2A workbook for the import + reconciliation flow
  (parses offline; no cloud needed).

## `tally-reference/`
- `AccountingVouchers.xlsx`, `AllAccountingMasters.xlsx` — the TallyPrime import
  templates the exporters target.
- `tallyprime-excel-import-reference.md` — notes on the Tally Excel import format.

Deployment and cost notes live in [`../docs/reference/`](../docs/reference/).
