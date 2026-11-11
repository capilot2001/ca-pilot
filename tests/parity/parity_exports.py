"""A9 parity gate — v1 vs v2 produce identical accounting output.

The migration promise is "logic unchanged" (P5). This driver proves it at the
output boundary: it runs a fixed set of invoice fixtures through classify and
every exporter, and compares the artifacts across versions.

Artifacts compared (all deterministic — no run-time dates in the content):
  - masters.xml / vouchers.xml        (text, byte-for-byte)
  - masters.xlsx / vouchers.xlsx      (as a cell grid per sheet)
  - reconcile(batch)                  (the ReconSummary JSON)

Usage:
  # golden captured from v1 (run with v1 on PYTHONPATH):
  PYTHONPATH=/path/to/v1-finance/backend python tests/parity/parity_exports.py \
      --version v1 --emit tests/parity/golden
  # gate (run with v2 on PYTHONPATH) — this is what re-runs in CI:
  PYTHONPATH=.:server:services/ocr python tests/parity/parity_exports.py \
      --version v2 --check tests/parity/golden

The gate (--check) needs only v2 + the committed golden; v1 is not required to
re-run it. Company identity is pinned via env so classify decides the same way
in both versions.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

# Pin the CA-client identity so classify derives the same direction / nature /
# ledgers in both versions (v1 config.py and v2 domain/config.py read these).
os.environ.setdefault("COMPANY_NAME", "Parity Co")
os.environ.setdefault("COMPANY_GSTIN", "21AAAHN9743B1ZL")
os.environ.setdefault("COMPANY_STATE_CODE", "21")
os.environ.setdefault("COMPANY_STOCK", "1")
os.environ.setdefault("LEDGERFLOW_LLM", "0")

HERE = Path(__file__).resolve().parent
FIXTURES = json.loads((HERE / "fixtures.json").read_text())


def _modules(version: str):
    """Import the classify + exporters + reconcile for the requested version."""
    if version == "v1":
        import app.classify as classify_mod
        import app.excel_export as excel
        import app.xml_export as xml
        import app.reconcile as reconcile_mod
        from app.models import Invoice
    else:
        import app.domain.classify as classify_mod
        import app.domain.excel_export as excel
        import app.domain.xml_export as xml
        import app.domain.reconcile as reconcile_mod
        from shared.models import Invoice
    return classify_mod.classify, excel, xml, reconcile_mod.reconcile, Invoice


def _cell(v):
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def _xlsx_cells(data: bytes) -> dict:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), data_only=False)
    return {ws.title: [[_cell(c.value) for c in row] for row in ws.iter_rows()]
            for ws in wb.worksheets}


def artifacts(version: str) -> dict:
    classify, excel, xml, reconcile, Invoice = _modules(version)
    invs = [classify(Invoice.model_validate(d)) for d in FIXTURES]
    return {
        "masters.xml": xml.build_masters_xml(invs),
        "vouchers.xml": xml.build_vouchers_xml(invs),
        "masters_xlsx_cells": _xlsx_cells(excel.build_masters_workbook(invs)),
        "vouchers_xlsx_cells": _xlsx_cells(excel.build_vouchers_workbook(invs)),
        "reconcile": reconcile(invs).model_dump(),
    }


def _write(d: Path, arts: dict) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for name in ("masters.xml", "vouchers.xml"):
        (d / name).write_text(arts[name])
    for name in ("masters_xlsx_cells", "vouchers_xlsx_cells", "reconcile"):
        (d / f"{name}.json").write_text(json.dumps(arts[name], indent=2, sort_keys=True))


def _check(d: Path, arts: dict) -> int:
    def load_text(n): return (d / n).read_text()
    def load_json(n): return json.loads((d / f"{n}.json").read_text())

    failures = 0
    for name in ("masters.xml", "vouchers.xml"):
        if arts[name] != load_text(name):
            print(f"  MISMATCH {name}"); failures += 1
        else:
            print(f"  ok  {name} ({len(arts[name])} chars)")
    for name in ("masters_xlsx_cells", "vouchers_xlsx_cells", "reconcile"):
        if arts[name] != load_json(name):
            print(f"  MISMATCH {name}"); failures += 1
        else:
            print(f"  ok  {name}")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["v1", "v2"], required=True)
    ap.add_argument("--emit")
    ap.add_argument("--check")
    args = ap.parse_args()

    arts = artifacts(args.version)
    print(f"[{args.version}] built artifacts for {len(FIXTURES)} fixtures")
    if args.emit:
        _write(Path(args.emit), arts)
        print(f"[{args.version}] golden written to {args.emit}")
        return 0
    if args.check:
        print(f"[{args.version}] checking against golden in {args.check}")
        fails = _check(Path(args.check), arts)
        print("PARITY OK" if not fails else f"PARITY FAILED ({fails} artifact(s) differ)")
        return 1 if fails else 0
    print("nothing to do: pass --emit DIR or --check DIR")
    return 2


if __name__ == "__main__":
    sys.exit(main())
