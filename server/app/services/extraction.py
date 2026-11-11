"""Extraction orchestration — "the code decides" half of v1's pipeline.

The reading pipeline (``services/ocr``) hands back pre-classify invoice
*readings*; this module runs the accounting decisions on them: ``classify`` per
reading, the batch-level flags that only the whole upload can see
(``flag_duplicates`` / ``flag_stock_conflicts``), and ``recompute`` after a user
edit. All of this is v1 ``pipeline.py`` logic, unchanged (P5) — only the reading
merge was moved out, and ``process_file`` now gets its readings through the
``InvoiceExtractor`` port instead of calling the pipeline directly.
"""
from __future__ import annotations

from typing import List

from app.domain.classify import classify
from app.ports.invoice_extractor import InvoiceExtractor
from shared.models import Invoice, Exception_, TaxBreakup


def process_file(extractor: InvoiceExtractor, file_bytes: bytes,
                 filename: str) -> List[Invoice]:
    """Read one uploaded file and classify every bill it holds.

    Mirrors v1 ``pipeline.process_file``: one file can hold several bills, and
    each returned invoice is fully classified. The reading comes through the
    port (in-process or, later, a remote OCR service) so this layer never knows
    how the page was read.
    """
    return [classify(inv) for inv in extractor.extract(file_bytes, filename)]


def recompute(inv: Invoice) -> Invoice:
    """Re-derive all computed fields after a user edits header/line data.
    Clears prior derived state so exceptions/assumptions don't accumulate."""
    inv.tax = TaxBreakup()
    inv.journal = []
    inv.exceptions = []
    inv.assumptions = []
    inv.itc_eligible = None
    inv.itc_remarks = ""
    # re-fill party state from a (possibly edited) GSTIN
    if inv.party_gstin and len(inv.party_gstin) >= 2:
        from app.domain.config import STATE_CODES
        sc = inv.party_gstin[:2]
        if sc in STATE_CODES:
            inv.party_state_code = sc
            inv.party_state = STATE_CODES[sc]
    return classify(inv)


def flag_stock_conflicts(invoices: List[Invoice]) -> None:
    """One stock item, one base unit.

    Two invoices spelling the same item with different units collapse into a
    single stock master (first one wins), and the voucher line that disagrees
    with it then fails on import with "Mismatch in Unit of Stock Items". Only
    the batch can see this, so it can't live in classify().
    """
    from app.domain.config import normalize_unit

    first: dict = {}
    for inv in invoices:
        if inv.entry_mode != "item":
            continue
        for it in inv.items:
            if not it.description:
                continue
            unit = normalize_unit(it.unit)
            seen_unit, seen_file = first.setdefault(
                it.description, (unit, inv.source_file))
            if seen_unit != unit:
                inv.exceptions.append(Exception_(
                    code="STOCK_UNIT_CONFLICT", severity="warning",
                    message=f"Stock item '{it.description}' is measured in "
                            f"'{unit}' here but '{seen_unit}' in "
                            f"'{seen_file}'. Tally keeps one base unit per item, "
                            f"so one of the two vouchers will be rejected with "
                            f"\"Mismatch in Unit of Stock Items\" — align the unit "
                            f"or give the items distinct names."))


def flag_duplicates(invoices: List[Invoice]) -> None:
    """Mark duplicate (direction, party_gstin, invoice_number) combinations."""
    seen = {}
    for inv in invoices:
        key = (inv.direction, inv.party_gstin, inv.invoice_number.strip().upper())
        if inv.invoice_number and key in seen:
            inv.exceptions.append(Exception_(
                code="DUPLICATE_INVOICE", severity="warning",
                message=f"Duplicate invoice number '{inv.invoice_number}' for the "
                        f"same party as '{seen[key]}'."))
        else:
            seen[key] = inv.source_file
