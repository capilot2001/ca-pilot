"""Reading pipeline: bytes -> parsed, LLM-merged Invoice *readings*.

This is the reading half of v1's ``pipeline.py`` (P5 — logic unchanged). It
reads a file into one Invoice per bill, merging three readings of each page
(column parser, PDF text layer, Gemini), and stops there: the result is a
*reading*, not an accounting decision. Classification, batch flags and
recompute — "the code decides" — moved to ``app.services.extraction`` on the
server (ADR-0010). The one change from v1 is that ``read_file`` returns the
pre-classify invoices instead of calling ``classify`` itself.
"""
from __future__ import annotations

import re
from typing import List, Optional

from . import llm_extract
from app.domain.config import COMPANY, STATE_CODES, STATE_NAME_TO_CODE
from .ocr import extract_text
from .parser import parse_invoice, split_documents
from shared.models import Invoice, LineItem, Exception_, Assumption
from app.domain.validate import state_code_from_gstin
from .ports import LLMInvoiceReader


from shared.models import TaxBreakup


# What a digital PDF's text layer is allowed to fill in when the OCR came back
# empty-handed. Deliberately a list rather than "every blank string on the
# model": everything below is *read off the page*, so a second reading of the
# same page can supply it. The classification fields are derived instead, and
# must come from classify() on the merged invoice -- never from a second parse.
_FALLBACK_FIELDS = (
    "party_name", "party_gstin", "party_state_code", "party_state",
    "party_address", "party_pincode",
    "invoice_number", "invoice_date", "invoice_date_display",
    "place_of_supply", "place_of_supply_code",
)


def _fill_blanks(inv: Invoice, layer: Invoice) -> None:
    """Fill fields OCR left blank from the PDF's own text layer.

    Only blanks: where both readings found something, the OCR wins, so what the
    user sees stays the thing the OCR engine actually read. A filled field is
    recorded as an assumption -- it is a value from a second source, and a
    reviewer should be able to see that on the invoice card.
    """
    filled = []
    for name in _FALLBACK_FIELDS:
        if not getattr(inv, name) and getattr(layer, name):
            setattr(inv, name, getattr(layer, name))
            filled.append(name)

    # direction comes from which GSTIN is the seller's, so it is only
    # meaningful alongside the GSTIN it was derived from
    if inv.direction == "unknown" and layer.direction != "unknown":
        inv.direction = layer.direction
        filled.append("direction")

    if not inv.items and layer.items:
        inv.items = layer.items
        filled.append("items")

    if filled:
        inv.ocr_engine = "google-vision + pdf-text-layer"
        inv.assumptions.append(Assumption(
            field=", ".join(filled),
            value="read from the PDF's text layer",
            reason="Cloud Vision did not find this on the page; the PDF's own "
                   "embedded text did."))


def _page_label(filename: str, group: List[int], single: bool) -> str:
    """Name this invoice's source. A file holding several bills has to say
    which one each voucher came from -- the CA checks the voucher against the
    page, and duplicate detection keys off the name."""
    if single:
        return filename
    pages = f"page {group[0] + 1}" if len(group) == 1 else \
            f"pages {group[0] + 1}-{group[-1] + 1}"
    return f"{filename} ({pages})"


def read_file(file_bytes: bytes, filename: str,
              reader: LLMInvoiceReader = llm_extract) -> List[Invoice]:
    """Read one uploaded file into one invoice *reading* per bill it contains.

    Three readings of the same page, in increasing order of authority: the
    caption-and-column parser over the OCR text, the PDF's own text layer for
    whatever that left blank, and -- where it is reachable -- Gemini, which
    reads the page as a document rather than as rows and so is the one that
    copes with a template nobody has seen before. The returned invoices are
    *pre-classify*: the server derives taxable values, tax, the journal and the
    direction from whichever reading won (``app.services.extraction``), so the
    accounting is the same however the page was read.
    """
    ex = extract_text(file_bytes, filename)
    groups = split_documents([p.rows for p in ex.pages])
    single = len(groups) <= 1

    out: List[Invoice] = []
    for group in groups:
        pages = [ex.pages[i] for i in group]
        rows = "\n".join(p.rows for p in pages)
        inv = parse_invoice(rows, "\n".join(p.plain for p in pages),
                            _page_label(filename, group, single), ex.engine)
        layer_plain = "\n".join(p.layer_plain for p in pages)
        if layer_plain.strip():
            _fill_blanks(inv, parse_invoice(
                "\n".join(p.layer_rows for p in pages), layer_plain,
                inv.source_file, "pdf-text-layer"))
        read = reader.read_invoice([p.image for p in pages], rows)
        if read is not None:
            apply_llm_reading(inv, read)
        elif reader.expected():
            # The reader was meant to run and could not (a quota blip that
            # outlasted its retries). Say so on the invoice: this one was read
            # by the fallback parser, which on an unfamiliar template can be
            # confidently wrong rather than obviously blank -- and a taxable
            # value that is off but plausible is the one error a CA scrolling
            # a batch will not catch.
            inv.exceptions.append(Exception_(
                code="LLM_READ_UNAVAILABLE", severity="warning",
                message="Gemini was unavailable for this invoice, so it was "
                        "read by the fallback parser alone. Check the line "
                        "items and the taxable value against the bill, or "
                        "re-run the extraction."))
        out.append(inv)
    return out


# ---------------------------------------------------------------------------
# merging Gemini's reading into the parsed invoice
# ---------------------------------------------------------------------------
def _direction_and_counterparty(read: "llm_extract.LLMInvoice"):
    """Which side of this invoice the client is on, and who the other side is.

    The model is deliberately not asked -- it returns the supplier and the
    buyer as printed, and the company's own GSTIN decides. That keeps the one
    judgement that changes an invoice's meaning (purchase vs sale, and so which
    ledgers and which GSTR return it lands in) out of the model's hands.
    """
    company = COMPANY.gstin.strip().upper()
    supplier, buyer = read.supplier, read.buyer
    if company and supplier.gstin == company:
        return "sale", buyer
    if company and buyer.gstin == company:
        return "purchase", supplier
    # Neither side carries the client's GSTIN -- the same fallback the parser
    # uses, and the same reason: an unreadable company GSTIN is far more often
    # a bill the office received than one it issued.
    if supplier.gstin or supplier.name:
        return "purchase", supplier
    return "", None


def _state_of(party: "llm_extract.LLMParty") -> str:
    """The party's state code: from its GSTIN if it has one, else as printed.

    The printed one matters — an unregistered buyer has no GSTIN to derive it
    from, and without a state code the supply's nature is undeterminable and
    the voucher will not import.
    """
    code = state_code_from_gstin(party.gstin)
    if code:
        return code
    code = (party.state_code or "").strip().lstrip("0").zfill(2)
    if code in STATE_CODES:
        return code
    return STATE_NAME_TO_CODE.get((party.state_name or "").strip().lower(), "")


def apply_llm_reading(inv: Invoice, read: "llm_extract.LLMInvoice") -> None:
    """Overlay the model's reading on the parsed invoice.

    The model wins where it read something, because it is the reading that
    generalises; the parser's value stays wherever the model left a blank, so
    two readers can only add information, never remove it. Only *printed*
    fields are touched -- taxable_total, tax and the journal are left for
    classify() to derive.
    """
    direction, other = _direction_and_counterparty(read)
    if direction:
        inv.direction = direction
    if other is not None:
        if other.name:
            inv.party_name = other.name
        if other.gstin:
            inv.party_gstin = other.gstin
        if other.address:
            inv.party_address = other.address
        if other.pincode:
            inv.party_pincode = other.pincode
        code = _state_of(other)
        if code:
            inv.party_state_code = code
            inv.party_state = STATE_CODES.get(code, inv.party_state)

    if read.invoice_number:
        inv.invoice_number = read.invoice_number
    if read.invoice_date:
        _set_date(inv, read.invoice_date)

    pos = (read.place_of_supply_state_code or "").strip().lstrip("0").zfill(2)
    if pos not in STATE_CODES:
        pos = STATE_NAME_TO_CODE.get(
            (read.place_of_supply_state_name or "").strip().lower(), "")
    if pos:
        inv.place_of_supply_code = pos
        inv.place_of_supply = STATE_CODES[pos]

    items = [_line_item(i) for i in read.items if _line_item(i) is not None]
    if items:
        inv.items = items
    if read.invoice_total:
        inv.invoice_total = read.invoice_total
    if read.round_off is not None:
        inv.tax.round_off = read.round_off
    printed = TaxBreakup(cgst=read.cgst_amount or 0.0, sgst=read.sgst_amount or 0.0,
                         igst=read.igst_amount or 0.0, cess=read.cess_amount or 0.0)
    if printed.cgst or printed.sgst or printed.igst or printed.cess:
        inv.printed_tax = printed

    inv.ocr_engine = f"{inv.ocr_engine} + {llm_extract.model_name()}"


def _line_item(i: "llm_extract.LLMItem") -> Optional[LineItem]:
    """One model-read row as a LineItem, or None if it carries no value.

    A row with no amount cannot be posted and would only add an empty
    inventory entry that Tally rejects.
    """
    if i.taxable_value is None and i.rate is None:
        return None
    taxable = i.taxable_value
    if taxable is None and i.quantity and i.rate:
        taxable = round(i.quantity * i.rate * (1 - (i.discount_percent or 0) / 100), 2)
    if taxable is None:
        return None
    # A lump-sum charge row prints a rate and an amount but leaves the quantity
    # column empty ("Add FREIGHT CHARGES ... 120000.00"). An inventory entry
    # with no quantity has no rate either, so Tally gets a stock line it cannot
    # re-multiply; one unit at the printed rate is the same money and imports.
    quantity = i.quantity
    if not quantity and i.rate:
        quantity = round(taxable / i.rate, 4) or None
    return LineItem(
        description=(i.description or "").strip(), hsn_sac=i.hsn_sac,
        quantity=quantity, unit=i.unit, rate=i.rate,
        disc_pct=i.discount_percent, gst_rate=i.gst_rate_percent,
        taxable_value=taxable, amount=taxable)


def _set_date(inv: Invoice, iso: str) -> None:
    """Accept the model's ISO date only if it really is one."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso.strip())
    if not m:
        return
    y, mo, d = (int(x) for x in m.groups())
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return
    inv.invoice_date = f"{y:04d}-{mo:02d}-{d:02d}"
    inv.invoice_date_display = f"{d}-{_MONTH_NAMES[mo - 1]}-{y}"


_MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
