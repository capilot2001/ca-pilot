# Parity gate — v1 vs v2 produce identical accounting output (A9)

The migration promise is **logic unchanged** (P5). This gate proves it at the
output boundary: the same invoice fixtures run through `classify` and every
exporter in each version must produce identical artifacts.

## Files
- `fixtures.json` — 4 pre-classify invoice readings (inter-state purchase 18%,
  intra-state purchase 12% two-line, inter-state sale 5%, exempt purchase 0%),
  with real-check-digit GSTINs so vouchers are not dropped as INVALID_GSTIN.
- `golden/` — artifacts captured from **v1**: `masters.xml`, `vouchers.xml`,
  `masters_xlsx_cells.json`, `vouchers_xlsx_cells.json`, `reconcile.json`.
- `parity_exports.py` — the driver: builds the artifacts for a version and
  either `--emit`s them (golden) or `--check`s against golden.
- `gen_fixtures.py` — regenerates `fixtures.json` (uses v2 models + valid GSTINs).

## Run the gate (v2 only — this is what CI runs)
```
PYTHONPATH=.:server:services/ocr python tests/parity/parity_exports.py \
    --version v2 --check tests/parity/golden
```
Exit 0 and `PARITY OK` means v2's classify + exporters match v1 byte-for-byte.

## Re-capture golden from v1 (only if fixtures change)
```
PYTHONPATH=/path/to/Codebase/v1-finance/backend python tests/parity/parity_exports.py \
    --version v1 --emit tests/parity/golden
```

## What is compared (all deterministic — no run-time dates in the content)
masters/vouchers XML byte-for-byte; masters/vouchers XLSX as a per-sheet cell
grid; and `reconcile(batch)`'s summary JSON. The recon XLSX/PDF formatting layer
is not diffed directly (reportlab/zip embed timestamps); its inputs are covered
by the `reconcile` JSON comparison. OCR/LLM reading is out of scope here — this
gate covers the deterministic accounting + export half.
