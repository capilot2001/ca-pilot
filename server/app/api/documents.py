"""Extraction, GSTR-2A import, reconciliation and recompute endpoints.

Behaviour is v1 main.py's: one upload can hold several bills; a per-file error
is surfaced as an invoice carrying an error exception rather than failing the
whole batch; batch-level flags run across the result. The only change is that
``/extract`` reads through the injected ``InvoiceExtractor`` port, and the
orchestration helpers come from ``app.services.extraction``.
"""
from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.deps import get_extractor
from app.domain import gstr2a
from app.domain.classify import classify
from app.domain.reconcile import reconcile
from app.ports.invoice_extractor import InvoiceExtractor
from app.services.extraction import (flag_duplicates, flag_stock_conflicts,
                                     process_file, recompute)
from shared.models import Exception_, Invoice

from .schemas import InvoiceBatch

router = APIRouter(prefix="/api", tags=["documents"])

Extractor = Annotated[InvoiceExtractor, Depends(get_extractor)]


# ---- extraction ------------------------------------------------------------
@router.post("/extract")
async def extract(extractor: Extractor, files: List[UploadFile] = File(...)):
    invoices: List[Invoice] = []
    for f in files:
        data = await f.read()
        try:
            # one file can hold several bills -- a CA scans a stack into one PDF
            invoices.extend(process_file(extractor, data, f.filename))
        except Exception as exc:  # noqa: BLE001 - surface as a per-file error
            inv = Invoice(source_file=f.filename, direction="unknown")
            inv.exceptions.append(Exception_(
                code="EXTRACTION_FAILED", severity="error",
                message=f"Could not process file: {exc}"))
            invoices.append(inv)
    flag_duplicates(invoices)
    flag_stock_conflicts(invoices)
    return JSONResponse([i.model_dump() for i in invoices])


# ---- GSTR-2A import (SOP 11.3) ---------------------------------------------
@router.post("/import/gstr2a")
async def import_gstr2a(files: List[UploadFile] = File(...)):
    """Ingest GSTR-2A Excel downloads as money-only purchase vouchers."""
    invoices: List[Invoice] = []
    for f in files:
        data = await f.read()
        try:
            rows = gstr2a.parse_gstr2a(data, f.filename)
        except Exception as exc:  # noqa: BLE001 - surface as a per-file error
            inv = Invoice(source_file=f.filename, source="gstr2a", direction="purchase")
            inv.exceptions.append(Exception_(
                code="GSTR2A_PARSE_FAILED", severity="error",
                message=f"Could not read GSTR-2A workbook: {exc}"))
            invoices.append(inv)
            continue
        if not rows:
            inv = Invoice(source_file=f.filename, source="gstr2a", direction="purchase")
            inv.exceptions.append(Exception_(
                code="GSTR2A_NO_ROWS", severity="error",
                message="No B2B rows could be mapped in this workbook. Check that "
                        "it is an unmodified GSTR-2A download from the GST portal."))
            invoices.append(inv)
            continue
        invoices.extend(classify(r) for r in rows)
    flag_duplicates(invoices)
    flag_stock_conflicts(invoices)
    return JSONResponse([i.model_dump() for i in invoices])


# ---- GSTR-2A vs books reconciliation (SOP 12) ------------------------------
@router.post("/reconcile")
def reconcile_batch(batch: InvoiceBatch):
    return JSONResponse(reconcile(batch.invoices).model_dump())


# ---- recompute after edits -------------------------------------------------
@router.post("/recompute")
def recompute_batch(batch: InvoiceBatch):
    out = [recompute(inv) for inv in batch.invoices]
    flag_duplicates(out)
    flag_stock_conflicts(out)
    return JSONResponse([i.model_dump() for i in out])
