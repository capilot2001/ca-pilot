"""Generate TallyPrime-importable Excel workbooks.

  * Masters workbook  -> Ledger sheet (matches AllAccountingMasters.xlsx headers
    + the GST columns Tally needs) plus Stock Item and Unit sheets that carry the
    GST rate on the item master itself.
  * Vouchers workbook -> Accounting Voucher sheet (matches AccountingVouchers.xlsx
    headers) with item-wise rows.

Column headers are written EXACTLY as spelled in the "Read Me" worksheet of
Tally's own sample files (AllAccountingMasters.xlsx / AccountingVouchers.xlsx,
both in the repo root) — including the trailing space in "Type of Duty/Tax " and
"Change Mode ". Tally matches mapping-template fields on that literal string, so
a renamed header silently maps to nothing.
"""
from __future__ import annotations

import io
from datetime import date
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from . import config as cfg
from .config import COMPANY
from .masters import collect_masters, registration_type
from .models import Invoice

_HEAD_FONT = Font(bold=True, color="FFFFFF")
_HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
_DATE_FMT = "DD-MMM-YYYY"

# Tally resolves an HSN/GST block only when the master says the details live on
# the master itself; the default ("As per Company/Group") makes it ignore every
# rate column we write. Same string as SOURCEOF*DETAILS in the XML path.
_SPECIFY = "Specify Details Here"


def _write_header(ws, headers):
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL
    ws.freeze_panes = "A2"


def _d(iso: str):
    """ISO date -> a real Excel date cell.

    Written as a date rather than a string so Tally reads it through Excel's
    serial number instead of guessing DD/MM vs MM/DD from the locale.

    An unreadable date falls back to the end of the current month rather than
    to a blank cell: Voucher Date is mandatory, and a blank one fails the row.
    """
    try:
        return date.fromisoformat((iso or "")[:10])
    except ValueError:
        return date.fromisoformat(cfg.end_of_current_month())


def _format_dates(ws, headers):
    for i, h in enumerate(headers, start=1):
        if "Date" in h or h.endswith("Applicable From"):
            for cell in ws.iter_cols(min_col=i, max_col=i, min_row=2):
                for c in cell:
                    c.number_format = _DATE_FMT


# ---------------------------------------------------------------------------
# MAPPING TEMPLATE CRIB SHEET
# ---------------------------------------------------------------------------
def _add_mapping_sheet(wb, blocks, notes=()):
    """Write the mapping template out in TallyPrime's own grid shape.

    Tally never reads this sheet. It exists because a user-defined Excel file is
    not importable on its own — someone has to key a Mapping Template against it
    first (reference doc §4 for masters, §5 for transactions), and that screen
    asks for exactly the four columns below plus the row/column settings. Every
    pair is written out here so building the template is transcription instead
    of guesswork, and so the same template can be rebuilt on another machine.

    Column headers in this workbook are deliberately spelled the way Tally's own
    field list spells them, so each row maps onto the field of the same name.
    """
    ws = wb.create_sheet("Mapping Template")
    ws.append(["TallyPrime mapping template — build this once, reuse every import"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=12)
    ws.append([])

    for b in blocks:
        headers = b["headers"]
        last = get_column_letter(len(headers))
        for row in (
            [f"Worksheet: {b['sheet']}"],
            [f"Alt+O (Import) → Manage → Mapping Templates → {b['kind']} → Create"],
            [b["target_label"], b["target_value"]],
            ["Save Mapping Template for", "This Company"],
            ["Excel Data has column headers", "Yes"],
            ["Row no. for column headers", 1],
            ["Import Data from row", 2, "to", "(blank = last row with data)"],
            ["Import Data from column", "A", "to", last],
            [],
            ["Field (TallyPrime)", "Column Header (Excel)", "Column (Excel)",
             "Fixed Value"],
        ):
            ws.append(row)
        head_row = ws.max_row
        ws.cell(row=head_row - 9, column=1).font = Font(bold=True)
        for c in range(1, 5):
            cell = ws.cell(row=head_row, column=c)
            cell.font = _HEAD_FONT
            cell.fill = _HEAD_FILL
        for i, h in enumerate(headers, start=1):
            # The Tally field name is the header minus the trailing space some
            # of them carry in Tally's sample files ("Change Mode ").
            ws.append([h.strip(), h, get_column_letter(i), ""])
        ws.append([])
        ws.append([])

    for note in notes:
        ws.append([note])


# ---------------------------------------------------------------------------
# MASTERS
# ---------------------------------------------------------------------------
LEDGER_HEADERS = [
    "Name", "Group Name", "Mailing Name", "Address", "State", "Country",
    "Pincode", "Ledger - Opening Balance", "Ledger Opening Balance - Dr/Cr",
    "Maintain balances bill-by-bill", "GST Applicability",
    "HSN/SAC - Applicable From", "HSN/SAC Details", "HSN/SAC", "HSN Description",
    "GST Rate - Applicable From", "GST Rate Details", "GST - Taxability Type",
    "IGST Rate", "CGST Rate", "SGST/UTGST Rate", "Type of Supply",
    "Type of Duty/Tax ", "Tax Type (GST)", "GST Registration - Applicable From",
    "GST Registration Type", "GST Registration - Assessee of Other Territory",
    "GST Registration - GSTIN/UIN", "Place of Supply (for Outwards)",
    "Type of Ledger",
]

STOCK_HEADERS = [
    "Name", "Under", "Units", "GST Applicability",
    "HSN/SAC - Applicable From", "HSN/SAC Details", "HSN/SAC", "HSN Description",
    "GST Rate - Applicable From", "GST Rate Details", "GST - Taxability Type",
    "IGST Rate", "CGST Rate", "SGST/UTGST Rate", "Type of Supply",
]


def build_masters_workbook(invoices: List[Invoice]) -> bytes:
    ms = collect_masters(invoices)
    af = _d(ms.applicable_from)
    wb = Workbook()

    # ---- Ledger sheet ----
    ws = wb.active
    ws.title = "Ledger"
    _write_header(ws, LEDGER_HEADERS)

    def row(**k):
        ws.append([k.get(h, "") for h in LEDGER_HEADERS])

    # Party ledgers. "GST Applicability" is deliberately absent — it is not a
    # field on a Sundry Debtors/Creditors ledger, and supplying it makes Tally
    # reject the master. Registration details go in the GST Registration block.
    for p in ms.parties.values():
        row(**{
            "Name": p.name, "Group Name": p.parent, "Mailing Name": p.name,
            "Address": p.address, "State": p.state, "Country": "India",
            "Pincode": p.pincode,
            # Off, deliberately, on the EXCEL path only. Tally's default voucher
            # mapping has no bill-allocation columns, so these vouchers cannot
            # declare a New Ref — and a bill-wise ledger posted without one is
            # an import exception on every single voucher. The XML path does
            # carry the allocation and keeps this on (see _party_ledger_xml).
            "Maintain balances bill-by-bill": "No",
            "GST Registration - Applicable From": af,
            "GST Registration Type": p.reg_type,
            "GST Registration - Assessee of Other Territory": "No",
            "GST Registration - GSTIN/UIN": p.gstin,
            "Place of Supply (for Outwards)": p.place_of_supply,
        })

    # Purchase / sales nominal ledgers.
    for n in ms.nominals.values():
        r = {
            "Name": n.name, "Group Name": n.parent,
            "GST Applicability": "Applicable",
            "Type of Supply": "Goods",
        }
        # Money-only vouchers reference no stock item, so the taxability and the
        # rate have to sit on this ledger — and "GST Rate Details" has to point
        # at the ledger, or the rate columns below are ignored.
        if n.money_only:
            half = round(n.gst_rate / 2, 2) if n.gst_rate else 0
            r.update({
                "GST Rate - Applicable From": af,
                "GST Rate Details": _SPECIFY,
                "GST - Taxability Type": n.taxability,
                "IGST Rate": n.gst_rate or 0,
                "CGST Rate": half, "SGST/UTGST Rate": half,
            })
        row(**r)

    # Tax ledgers. A Duties & Taxes ledger has no GST applicability of its own.
    for t in ms.taxes.values():
        row(**{
            "Name": t.name, "Group Name": "Duties & Taxes",
            "Type of Duty/Tax ": "GST", "Tax Type (GST)": t.tax_type,
        })

    # Round off. Left as a plain indirect expense rather than Type of Ledger =
    # "Invoice Rounding": that setting makes Tally compute its own rounding on
    # top of the amount we already post, which breaks the voucher balance.
    if ms.need_round_off:
        row(**{"Name": cfg.LEDGER_ROUND_OFF, "Group Name": "Indirect Expenses",
               "GST Applicability": "Not Applicable"})

    _format_dates(ws, LEDGER_HEADERS)

    # ---- Stock Item sheet (GST rate on the master) ----
    si = wb.create_sheet("Stock Item")
    _write_header(si, STOCK_HEADERS)
    for s in ms.stock_items.values():
        half = round(s.gst_rate / 2, 2) if s.gst_rate else 0
        si.append([
            s.name, "Primary", s.unit, "Applicable",
            af if s.hsn else "", _SPECIFY if s.hsn else "", s.hsn,
            s.name if s.hsn else "",
            af, _SPECIFY, s.taxability,
            s.gst_rate or 0, half, half, "Goods",
        ])
    _format_dates(si, STOCK_HEADERS)

    # ---- Unit sheet ----
    # Both "Symbol" and "Unit Quantity Code (UQC)" are spelled as TallyPrime's
    # Unit Creation screen labels them — a unit's name field is "Symbol" there,
    # not "Name", so a "Name" header maps to nothing and the unit imports with
    # no symbol. Without the UQC the unit imports incomplete, and either way
    # every stock item standing on it then fails to resolve.
    unit_headers = ["Symbol", "Formal Name", "Unit Quantity Code (UQC)",
                    "Type", "Decimal Places"]
    us = wb.create_sheet("Unit")
    _write_header(us, unit_headers)
    for u in ms.units:
        us.append([u, cfg.unit_formal_name(u), cfg.unit_uqc(u), "Simple",
                   cfg.UNIT_DECIMALS])

    # Order matters on import: a stock item needs its Unit, and a voucher needs
    # every master it names (reference doc §2.1).
    _add_mapping_sheet(wb, [
        {"sheet": "Unit", "kind": "MASTERS",
         "target_label": "Type of Master", "target_value": "Unit",
         "headers": unit_headers},
        {"sheet": "Ledger", "kind": "MASTERS",
         "target_label": "Type of Master", "target_value": "Ledger",
         "headers": LEDGER_HEADERS},
        {"sheet": "Stock Item", "kind": "MASTERS",
         "target_label": "Type of Master", "target_value": "Stock Item",
         "headers": STOCK_HEADERS},
    ], notes=[
        "Import in this order: Unit, then Ledger, then Stock Item — a stock "
        "item whose Unit does not exist yet is rejected.",
        "Import all of this workbook BEFORE the vouchers workbook: a voucher "
        "naming a ledger or stock item that does not exist fails.",
        "Alt+O → Import → Masters, then set 'Behaviour of Import if Masters "
        "already exists' before running, and use Preview Import Summary first.",
        "Every 'Applicable From' date in this workbook is 1 April of the "
        "financial year the batch's earliest invoice falls in. GST rates and "
        "HSN codes are notified per financial year, and a block dated after a "
        "voucher makes Tally resolve that voucher's rate to 0% without saying "
        "so — next year's batch adds its own 1 April block alongside this one.",
    ])

    _autosize(wb)
    return _to_bytes(wb)


# ---------------------------------------------------------------------------
# VOUCHERS
# ---------------------------------------------------------------------------
# AccountingVouchers.xlsx's own 14 columns first, verbatim — same order, same
# spelling (including the trailing space in "Change Mode ") — so a mapping
# template already keyed against Tally's sample file still lines up on them.
#
# After those come the party (Buyer/Supplier) block. Every one of these is a
# real field on the "Accounting Voucher (Read Me)" list, spelled as that list
# spells it ("Bill to/from", "Is Bill of Entry available" — Tally's own casing,
# not the title-case a hand-built sheet tends to use). They repeat on the
# voucher what the party ledger master already says, which is what Tally's Party
# Details screen holds: a voucher that states them cannot pick up a stale or
# half-created party master, and an unregistered party stops defaulting to
# Regular. An added column is only inert if the mapping template does not map
# it, so the Mapping Template sheet lists all of them — see _add_mapping_sheet.
#
# "Buyer/Supplier - Pincode" is deliberately NOT repeated in the POS block: it
# is a single Tally field, already carried at column 5, and two columns claiming
# one field cannot both be mapped.
#
# What is still left off travels a different way:
#   * unit of measure — off the stock item's base unit, and "Item Rate per";
#   * actual quantity — Tally defaults it to the billed quantity;
#   * per-line discount — folded into the exported rate, see _item_rate().
VOUCHER_HEADERS = [
    "Voucher Date", "Voucher Type Name", "Voucher Number",
    "Buyer/Supplier - Address", "Buyer/Supplier - Pincode", "Ledger Name",
    "Ledger Amount", "Ledger Amount Dr/Cr", "Item Name", "Billed Quantity",
    "Item Rate", "Item Rate per", "Item Amount", "Change Mode ",
    "Buyer/Supplier - Bill to/from", "Buyer/Supplier - Address Type",
    "Buyer/Supplier - Mailing Name", "Buyer/Supplier - Country",
    "Buyer/Supplier - State", "Buyer/Supplier - GST Registration Type",
    "Buyer/Supplier - Assessee of Other Territory",
    "Buyer/Supplier - GSTIN/UIN", "Buyer/Supplier - Is Bill of Entry available",
    "Buyer/Supplier - Place of Supply", "Buyer/Supplier - Country (POS)",
]

# The 14 columns Tally's own sample file ships with, in its order — everything
# after them is this workbook's addition (verify_e2e [4b] holds the prefix).
TALLY_SAMPLE_VOUCHER_COLS = 14

_COL = {h: i for i, h in enumerate(VOUCHER_HEADERS)}


def build_vouchers_workbook(invoices: List[Invoice]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Accounting Voucher"
    _write_header(ws, VOUCHER_HEADERS)

    for inv in invoices:
        if inv.direction not in ("purchase", "sale") or inv.has_errors:
            continue
        _emit_voucher_rows(ws, inv)

    _format_dates(ws, VOUCHER_HEADERS)
    _add_mapping_sheet(wb, [
        {"sheet": "Accounting Voucher", "kind": "TRANSACTIONS",
         "target_label": "Type of Voucher", "target_value":
             f"{cfg.VOUCHER_TYPE_SALES} / {cfg.VOUCHER_TYPE_PURCHASE} "
             f"(each row states its own in 'Voucher Type Name')",
         "headers": VOUCHER_HEADERS},
    ], notes=[
        "Columns A-N are AccountingVouchers.xlsx's own 14, unchanged and in "
        "order, so a template already keyed against Tally's sample file still "
        "lines up on them. Columns O-Y are the Buyer/Supplier (Party Details) "
        "block — every one a field on Tally's own list, and every one on the "
        "Mapping Template sheet below. Map ALL of them: an added column left "
        "unmapped is what errors the import, not the column itself.",
        "Voucher Date is the date printed on the invoice, carried through "
        "unchanged. Do not overwrite it with the posting month — the GST "
        "master blocks are dated 1 April of that invoice's financial year "
        "precisely so back-dated vouchers still resolve their rate.",
        "Layout: Ledger Details from Multiple Rows. One voucher spans several "
        "rows — the first row of each group carries the date, voucher number "
        "and party address; the rows under it are its remaining ledger lines "
        "and are blank in those columns (reference doc §1.3).",
        "Import the masters workbook first — the unit of measure is read off "
        "the stock item's base unit, and the party ledger has to exist before "
        "a voucher can name it. The party's GSTIN, state, registration type "
        "and place of supply are on both: the master holds them, and columns "
        "O-Y restate them on the voucher so it cannot pick up a half-created "
        "party.",
        "Alt+O → Import → Transactions. Set 'Behaviour of Import when "
        "exceptions exist' to 'Record Exceptions and Import' so one bad invoice "
        "does not stop the batch, and check the Exceptions Report afterwards.",
    ])
    _autosize(wb)
    return _to_bytes(wb)


def _item_rate(item):
    """(billed quantity, rate) for one item row, as Tally will re-multiply them.

    Tally recomputes the line as rate x quantity, so the rate on the wire has to
    be the one that reproduces Item Amount — otherwise the recomputed line stops
    matching the tax and party rows and the voucher is rejected as out of
    balance. On any row carrying a discount the printed rate is a GROSS rate
    (210.00 against an amount of 15,750 at 40% off), and with the "Disc%" column
    gone there is nowhere to declare that, so the rate is derived from the
    amount instead. The discount is still visible on the invoice card in the UI.

    The quantity is rounded to what the Unit master allows first, and the rate
    derived from the rounded figure, so the product holds after Tally rounds.
    """
    if not item.quantity:
        return "", ""
    qty = round(item.quantity, cfg.UNIT_DECIMALS)
    return qty, round(abs(item.taxable_value or 0) / abs(qty), 4)


def _emit_voucher_rows(ws, inv: Invoice):
    vt = cfg.VOUCHER_TYPE_PURCHASE if inv.direction == "purchase" else cfg.VOUCHER_TYPE_SALES
    is_purchase = inv.direction == "purchase"
    item_dc = "Dr" if is_purchase else "Cr"
    # SOP 8 — Tally's "Change Mode" column selects the voucher entry mode.
    change_mode = "Item Invoice" if inv.entry_mode == "item" else "Accounting Invoice"
    party = inv.party_name or ("Sundry Creditor" if is_purchase else "Sundry Debtor")
    party_dc = "Cr" if is_purchase else "Dr"
    first = True

    # Party Details, written onto the voucher's first row alongside the rest of
    # the header fields. Same values the party ledger master carries (see
    # build_masters_workbook) — they have to agree, or the voucher imports with
    # a GST-registration exception against its own party.
    #
    # "Address Type" is left blank on purpose: it selects a Bill-to/Ship-to
    # variant Tally only asks for once consignee details are being entered, and
    # a value keyed there without them is rejected. Blank takes Tally's default.
    party_details = {
        "Buyer/Supplier - Bill to/from": party,
        "Buyer/Supplier - Address Type": "",
        "Buyer/Supplier - Mailing Name": party,
        "Buyer/Supplier - Address": inv.party_address,
        "Buyer/Supplier - Pincode": inv.party_pincode,
        "Buyer/Supplier - Country": "India",
        "Buyer/Supplier - State": inv.party_state,
        "Buyer/Supplier - GST Registration Type": registration_type(inv),
        "Buyer/Supplier - Assessee of Other Territory": "No",
        "Buyer/Supplier - GSTIN/UIN": inv.party_gstin,
        # Bill of Entry is the import-of-goods document; these are domestic
        # invoices, and "Yes" makes Tally demand a BoE number and date.
        "Buyer/Supplier - Is Bill of Entry available": "No",
        "Buyer/Supplier - Place of Supply": inv.place_of_supply or COMPANY.state,
        "Buyer/Supplier - Country (POS)": "India",
    }

    def emit(ledger, amount, dc, item=None):
        """One Excel row = one ledger line of the voucher.

        Only the first row of a voucher carries the header fields; blank header
        cells are how Tally's "Ledger Details from Multiple Rows" layout marks a
        continuation row of the same voucher.
        """
        nonlocal first
        r = [""] * len(VOUCHER_HEADERS)
        if first:
            # The invoice's OWN date, exactly as it was read off the document —
            # never today's date or a month-end stand-in. A voucher whose date
            # could not be read is an error-level exception and never reaches
            # this function, so _d()'s fallback is a backstop, not a default.
            r[_COL["Voucher Date"]] = _d(inv.invoice_date)
            r[_COL["Voucher Type Name"]] = vt
            r[_COL["Voucher Number"]] = inv.invoice_number
            r[_COL["Change Mode "]] = change_mode
            for h, v in party_details.items():
                r[_COL[h]] = v
        r[_COL["Ledger Name"]] = ledger
        r[_COL["Ledger Amount"]] = round(amount, 2)
        r[_COL["Ledger Amount Dr/Cr"]] = dc
        if item is not None:
            qty, rate = _item_rate(item)
            r[_COL["Item Name"]] = item.description
            r[_COL["Billed Quantity"]] = qty
            r[_COL["Item Rate"]] = rate
            r[_COL["Item Rate per"]] = cfg.normalize_unit(item.unit)
            r[_COL["Item Amount"]] = round(item.taxable_value or 0, 2)
        ws.append(r)
        first = False

    # Party first in both directions: reference doc §1.3 makes the party the
    # "Top Ledger" of the fixed-column layout, and it puts the voucher header
    # fields on the party's row where Tally's own sample file has them.
    emit(party, inv.invoice_total, party_dc)
    if inv.entry_mode == "item":
        # item lines against the nominal ledger for the line's own GST rate
        for it in inv.items:
            emit(it.ledger or inv.accounting_classification,
                 it.taxable_value or 0, item_dc, item=it)
    else:
        # money-only: a single nominal-ledger line, no stock item or quantity
        emit(inv.accounting_classification, inv.taxable_total, item_dc)
    # taxes
    t = inv.tax
    if is_purchase:
        for amt, led in ((t.cgst, cfg.LEDGER_INPUT_CGST), (t.sgst, cfg.LEDGER_INPUT_SGST),
                         (t.igst, cfg.LEDGER_INPUT_IGST)):
            if amt:
                emit(led, amt, "Dr")
    else:
        for amt, led in ((t.cgst, cfg.LEDGER_OUTPUT_CGST), (t.sgst, cfg.LEDGER_OUTPUT_SGST),
                         (t.igst, cfg.LEDGER_OUTPUT_IGST)):
            if amt:
                emit(led, amt, "Cr")
    # round off
    if t.round_off:
        ro = t.round_off
        if is_purchase:
            emit(cfg.LEDGER_ROUND_OFF, abs(ro), "Dr" if ro > 0 else "Cr")
        else:
            emit(cfg.LEDGER_ROUND_OFF, abs(ro), "Cr" if ro > 0 else "Dr")


# ---------------------------------------------------------------------------
def _autosize(wb):
    for ws in wb.worksheets:
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(width + 2, 45)


def _to_bytes(wb) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
