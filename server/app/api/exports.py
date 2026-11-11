"""TallyPrime export endpoints (xlsx / xml) and the reconciliation report.

Each export recomputes its invoices first (so a client edit is always reflected)
and streams the bytes as a download — identical to v1 main.py.
"""
from __future__ import annotations

import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.domain import excel_export, recon_export, xml_export
from app.domain.reconcile import reconcile
from app.services.extraction import recompute

from .schemas import InvoiceBatch

router = APIRouter(prefix="/api/export", tags=["exports"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _stream(data: bytes, filename: str, media: str):
    return StreamingResponse(
        io.BytesIO(data), media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/masters-xlsx")
def export_masters_xlsx(batch: InvoiceBatch):
    invs = [recompute(i) for i in batch.invoices]
    data = excel_export.build_masters_workbook(invs)
    return _stream(data, "Tally_Masters.xlsx", _XLSX)


@router.post("/vouchers-xlsx")
def export_vouchers_xlsx(batch: InvoiceBatch):
    invs = [recompute(i) for i in batch.invoices]
    data = excel_export.build_vouchers_workbook(invs)
    return _stream(data, "Tally_Vouchers.xlsx", _XLSX)


@router.post("/masters-xml")
def export_masters_xml(batch: InvoiceBatch):
    invs = [recompute(i) for i in batch.invoices]
    data = xml_export.build_masters_xml(invs).encode("utf-8")
    return _stream(data, "Tally_Masters.xml", "application/xml")


@router.post("/vouchers-xml")
def export_vouchers_xml(batch: InvoiceBatch):
    invs = [recompute(i) for i in batch.invoices]
    data = xml_export.build_vouchers_xml(invs).encode("utf-8")
    return _stream(data, "Tally_Vouchers.xml", "application/xml")


@router.post("/recon-xlsx")
def export_recon_xlsx(batch: InvoiceBatch):
    """The reconciliation as a workbook — same figures the panel shows."""
    data = recon_export.build_recon_workbook(reconcile(batch.invoices))
    return _stream(data, recon_export.report_filename("xlsx"), _XLSX)


@router.post("/recon-pdf")
def export_recon_pdf(batch: InvoiceBatch):
    """The reconciliation as a signed-off-looking PDF, ready to forward."""
    data = recon_export.build_recon_pdf(reconcile(batch.invoices))
    return _stream(data, recon_export.report_filename("pdf"), "application/pdf")
