"""Read a GSTR-2A Excel download from the GST portal into Invoice records.

SOP 11.3. GSTR-2A carries supplier, invoice and tax fields but **no HSN and no
stock detail**, so everything sourced here posts money-only (see
``classify._determine_entry_mode``).

The portal's column headers vary between download vintages and between the
B2B / B2BA / CDNR sheets, so columns are matched by normalised alias rather
than exact string. Anything that cannot be mapped is reported as an exception
on the affected row instead of being guessed at (SOP 4 assumption rule).
"""
from __future__ import annotations

import io
import re
from typing import Dict, List, Optional

from openpyxl import load_workbook

from .config import COMPANY, STATE_CODES, STATE_NAME_TO_CODE
from .models import Invoice, LineItem, Assumption, Exception_, TaxBreakup
from .validate import state_code_from_gstin

# Sheets that carry inward B2B supplies. Amendment/credit-note sheets are read
# too; a credit note simply arrives with negative values.
_SHEET_HINTS = ("b2b", "cdnr", "b2ba", "cdnra")

# canonical field -> accepted header aliases (normalised: lowercase, alnum only)
_ALIASES: Dict[str, tuple] = {
    "gstin": (
        "gstinofsupplier", "gstinuinofsupplier", "suppliergstin", "gstin",
        "gstinuin",
    ),
    "party_name": (
        "tradelegalname", "legalname", "tradename", "nameofsupplier",
        "suppliername", "supplier",
    ),
    "invoice_number": (
        "invoicenumber", "invoiceno", "invoicedetailsinvoicenumber",
        "notenumber", "creditnotenumber", "documentnumber", "docno",
    ),
    "invoice_date": (
        "invoicedate", "invoicedetailsinvoicedate", "notedate", "documentdate",
        "docdate",
    ),
    "invoice_total": (
        "invoicevaluers", "invoicevalue", "totalinvoicevalue", "notevalue",
        "documentvalue",
    ),
    "place_of_supply": ("placeofsupply", "pos", "supplytype"),
    "rate": ("rate", "ratepercent", "gstrate", "taxrate"),
    "taxable_value": ("taxablevalue", "taxablevaluers", "taxableamount"),
    "igst": ("integratedtaxpaid", "integratedtax", "igst", "igstamount"),
    "cgst": ("centraltaxpaid", "centraltax", "cgst", "cgstamount"),
    "sgst": (
        "stateutterritorytaxpaid", "stateutterritorytax", "stateuttaxpaid",
        "stateuttax", "statetaxpaid", "statetax", "sgst", "sgstamount",
        "sgstutgst", "sgstutgstamount", "utgst",
    ),
    "cess": ("cesspaid", "cess", "cessamount"),
    "reverse_charge": ("reversecharge", "supplyattractreversecharge"),
}

_REQUIRED = ("gstin", "invoice_number", "invoice_date", "taxable_value")


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _num(v) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.\-]", "", str(v))
    try:
        return float(s)
    except ValueError:
        return None


def _date(v) -> tuple:
    """Return (iso, display). Accepts real datetimes and dd-mm-yyyy strings."""
    if v is None or v == "":
        return "", ""
    if hasattr(v, "year") and hasattr(v, "month"):
        return v.strftime("%Y-%m-%d"), v.strftime("%d-%b-%Y")
    s = str(v).strip()
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$", s)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        y = y + 2000 if y < 100 else y
        try:
            import datetime
            dt = datetime.date(y, mo, d)
            return dt.strftime("%Y-%m-%d"), dt.strftime("%d-%b-%Y")
        except ValueError:
            return "", ""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        import datetime
        try:
            dt = datetime.date(*(int(x) for x in m.groups()))
            return dt.strftime("%Y-%m-%d"), dt.strftime("%d-%b-%Y")
        except ValueError:
            return "", ""
    return "", ""


def _map_header_row(row) -> Dict[str, int]:
    """Map canonical field -> column index for one candidate header row."""
    found: Dict[str, int] = {}
    for idx, cell in enumerate(row):
        n = _norm(cell)
        if not n:
            continue
        for field, aliases in _ALIASES.items():
            if field in found:
                continue
            if n in aliases:
                found[field] = idx
                break
    return found


def _find_header(rows) -> tuple:
    """GSTR-2A downloads carry 3-5 title/banner rows above the real header, and
    sometimes a two-tier header. Scan the first 15 rows and keep the mapping
    that resolves the most fields."""
    best: Dict[str, int] = {}
    best_at = -1
    for i, row in enumerate(rows[:15]):
        m = _map_header_row(row)
        if len(m) > len(best):
            best, best_at = m, i
    return best, best_at


def parse_gstr2a(file_bytes: bytes, filename: str) -> List[Invoice]:
    """Parse every B2B-style sheet in the workbook into money-only Invoices."""
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    invoices: List[Invoice] = []

    sheets = [ws for ws in wb.worksheets if any(h in _norm(ws.title) for h in _SHEET_HINTS)]
    if not sheets:
        sheets = list(wb.worksheets)          # unnamed/renamed export — try all

    for ws in sheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        if not rows:
            continue
        colmap, header_at = _find_header(rows)
        missing = [f for f in _REQUIRED if f not in colmap]
        if missing:
            continue                          # not a data sheet; skip quietly

        for r in rows[header_at + 1:]:
            inv = _row_to_invoice(r, colmap, filename, ws.title)
            if inv is not None:
                invoices.append(inv)

    wb.close()
    return invoices


def _cell(row, colmap, field):
    idx = colmap.get(field)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def _row_to_invoice(row, colmap, filename: str, sheet: str) -> Optional[Invoice]:
    gstin = str(_cell(row, colmap, "gstin") or "").strip().upper()
    number = str(_cell(row, colmap, "invoice_number") or "").strip()
    taxable = _num(_cell(row, colmap, "taxable_value"))

    # blank / total / continuation rows
    if not gstin and not number:
        return None
    if taxable is None and not number:
        return None
    if _norm(gstin).startswith("total") or _norm(number).startswith("total"):
        return None

    inv = Invoice(
        source_file=f"{filename} [{sheet}]",
        ocr_engine="gstr2a-excel",
        source="gstr2a",
        direction="purchase",          # 2A is an inward-supply statement
        entry_mode="accounting",
        party_gstin=gstin,
        party_name=str(_cell(row, colmap, "party_name") or "").strip(),
        invoice_number=number,
    )

    sc = state_code_from_gstin(gstin)
    if sc:
        inv.party_state_code = sc
        inv.party_state = STATE_CODES[sc]

    iso, disp = _date(_cell(row, colmap, "invoice_date"))
    inv.invoice_date, inv.invoice_date_display = iso, disp

    _set_place_of_supply(inv, _cell(row, colmap, "place_of_supply"))

    rate = _num(_cell(row, colmap, "rate"))
    igst = _num(_cell(row, colmap, "igst")) or 0.0
    cgst = _num(_cell(row, colmap, "cgst")) or 0.0
    sgst = _num(_cell(row, colmap, "sgst")) or 0.0
    cess = _num(_cell(row, colmap, "cess")) or 0.0

    if rate is None and taxable:
        # 2A does not always print the rate; derive it from the tax actually paid
        tax_paid = igst + cgst + sgst
        if tax_paid:
            rate = round(tax_paid / taxable * 100, 2)
            inv.assumptions.append(Assumption(
                field="gst_rate", value=f"{rate}%",
                reason="Rate column absent in GSTR-2A; derived from tax paid / "
                       "taxable value."))

    # one synthetic line so downstream tax computation and rate-wise ledger
    # selection work exactly as they do for a scanned invoice
    inv.items.append(LineItem(
        description=f"GSTR-2A supply @ {rate or 0}%",
        taxable_value=taxable or 0.0,
        amount=taxable or 0.0,
        gst_rate=rate,
    ))
    inv.taxable_total = round(taxable or 0.0, 2)

    # what the supplier actually uploaded — drives the SOP 10 tax-head check
    inv.printed_tax = TaxBreakup(cgst=cgst, sgst=sgst, igst=igst, cess=cess)

    total = _num(_cell(row, colmap, "invoice_total"))
    if total is not None:
        inv.invoice_total = total

    rc = str(_cell(row, colmap, "reverse_charge") or "").strip().upper()
    if rc in ("Y", "YES"):
        inv.exceptions.append(Exception_(
            code="REVERSE_CHARGE", severity="warning",
            message="GSTR-2A marks this supply as attracting reverse charge; "
                    "tax is payable by the recipient. Verify the posting."))

    if not taxable:
        inv.exceptions.append(Exception_(
            code="MISSING_TAXABLE_VALUE", severity="error",
            message="Taxable value is missing or unreadable in the GSTR-2A row."))

    inv.raw_text = " | ".join(str(c) for c in row if c not in (None, ""))
    return inv


def _set_place_of_supply(inv: Invoice, raw):
    """POS in 2A is usually "27-Maharashtra"; sometimes just a name or a code."""
    s = str(raw or "").strip()
    if s:
        m = re.match(r"^\s*(\d{1,2})\s*[-–]\s*(.+)$", s)
        if m:
            code = m.group(1).zfill(2)
            if code in STATE_CODES:
                inv.place_of_supply_code = code
                inv.place_of_supply = STATE_CODES[code]
                return
        code = STATE_NAME_TO_CODE.get(s.lower())
        if code:
            inv.place_of_supply_code = code
            inv.place_of_supply = STATE_CODES[code]
            return
        if s.isdigit() and s.zfill(2) in STATE_CODES:
            inv.place_of_supply_code = s.zfill(2)
            inv.place_of_supply = STATE_CODES[s.zfill(2)]
            return
    # inward supply: place of supply is the recipient's (our) state
    inv.place_of_supply = COMPANY.state
    inv.place_of_supply_code = COMPANY.state_code
    inv.assumptions.append(Assumption(
        field="place_of_supply", value=COMPANY.state,
        reason="Place of Supply not present/parseable in the GSTR-2A row; "
               "inferred as the company's state for an inward supply."))
