"""Generate TallyPrime-importable XML (masters + vouchers).

Follows the documented Tally import schema:
    ENVELOPE > BODY > IMPORTDATA > REQUESTDATA > TALLYMESSAGE > {MASTER|VOUCHER}

Sign convention used throughout:
    debit  -> ISDEEMEDPOSITIVE=Yes, AMOUNT negative
    credit -> ISDEEMEDPOSITIVE=No,  AMOUNT positive

Two schema notes that drive most of the shape of this file:

  * TallyPrime Release 3.0 moved a party ledger's mailing and GST-registration
    details out of flat tags and into dated LEDMAILINGDETAILS.LIST /
    LEDGSTREGDETAILS.LIST blocks. Both forms are emitted — Tally ignores tags it
    does not recognise, so this imports cleanly on either side of 3.0 whereas
    the flat tags alone leave 3.x with "GST registration details are invalid or
    not specified".
  * Every dated block is stamped 1 April of the financial year the batch's
    earliest invoice falls in (see MasterSet.applicable_from / cfg.fy_start).
    GST rates and HSN codes are notified per financial year, and an
    APPLICABLEFROM later than the voucher date makes Tally resolve the rate to
    0% without complaining — an FY-start can never be later.
"""
from __future__ import annotations

import re
import uuid
from typing import List, Optional
from xml.sax.saxutils import escape

from . import config as cfg
from .config import COMPANY
from .masters import collect_masters
from shared.models import Invoice

_DUTYHEAD = {"CGST": "Central Tax", "SGST/UTGST": "State Tax", "IGST": "Integrated Tax"}

# XML 1.0 forbids these outright; OCR'd descriptions carry them often enough
# that leaving them in makes Tally reject the whole file as unparseable.
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Namespace for deterministic REMOTEIDs — the same invoice always exports the
# same id, giving the client a stable key back to the source document.
_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _e(v) -> str:
    # escape quotes too so values are safe in both element text and attributes
    return escape(_CTRL.sub("", "" if v is None else str(v)),
                  {'"': "&quot;", "'": "&apos;"})


def _ymd(iso: str) -> str:
    """ISO date -> Tally's YYYYMMDD. Empty falls back to the end of the current
    month — a voucher with no DATE is rejected outright."""
    return (iso or cfg.end_of_current_month()).replace("-", "")


def _envelope(report: str, body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<ENVELOPE>\n"
        " <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>\n"
        " <BODY>\n  <IMPORTDATA>\n"
        "   <REQUESTDESC>\n"
        f"    <REPORTNAME>{report}</REPORTNAME>\n"
        "    <STATICVARIABLES>\n"
        f"     <SVCURRENTCOMPANY>{_e(COMPANY.name)}</SVCURRENTCOMPANY>\n"
        "    </STATICVARIABLES>\n"
        "   </REQUESTDESC>\n"
        "   <REQUESTDATA>\n"
        f"{body}"
        "   </REQUESTDATA>\n"
        "  </IMPORTDATA>\n"
        " </BODY>\n"
        "</ENVELOPE>\n"
    )


def _messages(parts: List[str]) -> str:
    """Wrap each master/voucher in its OWN TALLYMESSAGE.

    Tally's own exports put exactly one object per TALLYMESSAGE, and that is the
    shape its importer is written against. Packing the whole batch into a single
    message is accepted inconsistently — objects after the first can be skipped,
    which then surfaces on the voucher pass as "Referenced master is missing"
    for a master that was in the file all along.
    """
    return "".join(
        '    <TALLYMESSAGE xmlns:UDF="TallyUDF">\n' + p + "\n    </TALLYMESSAGE>\n"
        for p in parts
    )


def _rate_rows(rate: float, indent: str = "        ") -> str:
    """The four GST duty-head rows Tally expects inside a GSTDETAILS.LIST."""
    if not rate:
        return ""
    half = round(rate / 2, 2)
    out = ""
    for head, val in (("CGST", half), ("SGST/UTGST", half), ("IGST", rate), ("Cess", 0)):
        out += (
            f"{indent}<RATEDETAILS.LIST>\n"
            f"{indent} <GSTRATEDUTYHEAD>{head}</GSTRATEDUTYHEAD>\n"
            f"{indent} <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n"
            f"{indent} <GSTRATE>{val}</GSTRATE>\n"
            f"{indent}</RATEDETAILS.LIST>\n"
        )
    return out


# ---------------------------------------------------------------------------
# MASTERS
# ---------------------------------------------------------------------------
def build_masters_xml(invoices: List[Invoice]) -> str:
    ms = collect_masters(invoices)
    af = _ymd(ms.applicable_from)
    parts: List[str] = []

    for u in ms.units:
        parts.append(_unit_xml(u))
    for p in ms.parties.values():
        parts.append(_party_ledger_xml(p, af))
    for n in ms.nominals.values():
        parts.append(_nominal_ledger_xml(n, af))
    for t in ms.taxes.values():
        parts.append(_tax_ledger_xml(t))
    if ms.need_round_off:
        parts.append(_roundoff_ledger_xml())
    for s in ms.stock_items.values():
        parts.append(_stock_item_xml(s, af))

    return _envelope("All Masters", _messages(parts))


def _unit_xml(name: str) -> str:
    n = _e(name)
    # A Unit whose formal name equals its symbol is rejected outright, so
    # unit_formal_name() returns "" rather than echoing the symbol.
    formal = cfg.unit_formal_name(name)
    # GSTREPUOM is the "Unit Quantity Code (UQC)" field on TallyPrime 3.x's Unit
    # Creation screen. Leaving it unset imports a unit GST cannot report
    # quantities in, and the stock items standing on it never resolve.
    return (f'     <UNIT NAME="{n}" ACTION="Create">\n'
            f"      <NAME>{n}</NAME>\n"
            f"      <ORIGINALNAME>{n}</ORIGINALNAME>\n"
            + (f"      <FORMALNAME>{_e(formal)}</FORMALNAME>\n" if formal else "")
            + f"      <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>\n"
            f"      <DECIMALPLACES>{cfg.UNIT_DECIMALS}</DECIMALPLACES>\n"
            f"      <GSTREPUOM>{_e(cfg.unit_uqc(name))}</GSTREPUOM>\n"
            f"     </UNIT>")


def _address_list(address: str, indent: str) -> str:
    """An ADDRESS.LIST block, or nothing at all when there is no address.

    Emitting an empty <ADDRESS/> writes a blank address line into the master
    rather than leaving the field unset.
    """
    if not address:
        return ""
    return (f'{indent}<ADDRESS.LIST TYPE="String">\n'
            f"{indent} <ADDRESS>{_e(address)}</ADDRESS>\n"
            f"{indent}</ADDRESS.LIST>\n")


def _party_ledger_xml(p, af: str) -> str:
    n = _e(p.name)
    return (
        f'     <LEDGER NAME="{n}" ACTION="Create">\n'
        f"      <NAME>{n}</NAME>\n"
        f"      <PARENT>{_e(p.parent)}</PARENT>\n"
        f"      <ISBILLWISEON>Yes</ISBILLWISEON>\n"
        f"      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>\n"
        # --- flat tags: pre-3.0 Tally reads these ---
        f"      <GSTREGISTRATIONTYPE>{_e(p.reg_type)}</GSTREGISTRATIONTYPE>\n"
        f"      <PARTYGSTIN>{_e(p.gstin)}</PARTYGSTIN>\n"
        f"      <GSTREGISTRATIONNUMBER>{_e(p.gstin)}</GSTREGISTRATIONNUMBER>\n"
        f"      <LEDSTATENAME>{_e(p.state)}</LEDSTATENAME>\n"
        f"      <PLACEOFSUPPLY>{_e(p.place_of_supply)}</PLACEOFSUPPLY>\n"
        f"      <PINCODE>{_e(p.pincode)}</PINCODE>\n"
        f"{_address_list(p.address, '      ')}"
        # --- Release 3.0+ dated blocks: what 3.x actually reads ---
        f"      <LEDMAILINGDETAILS.LIST>\n"
        f"       <APPLICABLEFROM>{af}</APPLICABLEFROM>\n"
        f"       <MAILINGNAME>{n}</MAILINGNAME>\n"
        f"{_address_list(p.address, '       ')}"
        f"       <STATE>{_e(p.state)}</STATE>\n"
        f"       <COUNTRY>India</COUNTRY>\n"
        f"       <PINCODE>{_e(p.pincode)}</PINCODE>\n"
        f"      </LEDMAILINGDETAILS.LIST>\n"
        f"      <LEDGSTREGDETAILS.LIST>\n"
        f"       <APPLICABLEFROM>{af}</APPLICABLEFROM>\n"
        f"       <GSTREGISTRATIONTYPE>{_e(p.reg_type)}</GSTREGISTRATIONTYPE>\n"
        f"       <GSTIN>{_e(p.gstin)}</GSTIN>\n"
        f"       <ISOTHTERRITORYASSESSEE>No</ISOTHTERRITORYASSESSEE>\n"
        f"       <PLACEOFSUPPLY>{_e(p.place_of_supply)}</PLACEOFSUPPLY>\n"
        f"      </LEDGSTREGDETAILS.LIST>\n"
        f"     </LEDGER>")


def _nominal_ledger_xml(n, af: str) -> str:
    """Purchase/Sales nominal ledger.

    In money-only (accounting invoice) mode there is no stock item to hold the
    GST rate, so the taxability and rate are pinned on the ledger master here —
    the same "Specify Details Here" pinning the stock item uses.
    """
    name = _e(n.name)
    gst_block = ""
    if n.money_only:
        gst_block = (
            f"      <GSTDETAILS.LIST>\n"
            f"       <APPLICABLEFROM>{af}</APPLICABLEFROM>\n"
            f"       <SOURCEOFGSTDETAILS>Specify Details Here</SOURCEOFGSTDETAILS>\n"
            f"       <TAXABILITY>{_e(n.taxability)}</TAXABILITY>\n"
            f"{_rate_rows(n.gst_rate)}"
            f"      </GSTDETAILS.LIST>\n"
        )
    return (
        f'     <LEDGER NAME="{name}" ACTION="Create">\n'
        f"      <NAME>{name}</NAME>\n"
        f"      <PARENT>{_e(n.parent)}</PARENT>\n"
        f"      <ISGSTAPPLICABLE>Applicable</ISGSTAPPLICABLE>\n"
        f"      <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>\n"
        f"{gst_block}"
        f"     </LEDGER>")


def _tax_ledger_xml(t) -> str:
    """A Duties & Taxes ledger.

    ISGSTAPPLICABLE is "Not Applicable" on purpose: the ledger *is* the tax, it
    is not a ledger that attracts tax, and marking it Applicable makes Tally
    reject the master.
    """
    name = _e(t.name)
    return (
        f'     <LEDGER NAME="{name}" ACTION="Create">\n'
        f"      <NAME>{name}</NAME>\n"
        f"      <PARENT>Duties &amp; Taxes</PARENT>\n"
        f"      <TAXTYPE>GST</TAXTYPE>\n"
        f"      <GSTDUTYHEAD>{_DUTYHEAD.get(t.tax_type, t.tax_type)}</GSTDUTYHEAD>\n"
        f"      <ISGSTAPPLICABLE>Not Applicable</ISGSTAPPLICABLE>\n"
        f"      <AFFECTSSTOCK>No</AFFECTSSTOCK>\n"
        f"      <ISBILLWISEON>No</ISBILLWISEON>\n"
        f"     </LEDGER>")


def _roundoff_ledger_xml() -> str:
    """Plain indirect expense — deliberately NOT a "Invoice Rounding" ledger.

    That ledger type makes Tally compute its own rounding on top of the
    round-off amount the voucher already posts, which unbalances the voucher.
    """
    name = _e(cfg.LEDGER_ROUND_OFF)
    return (
        f'     <LEDGER NAME="{name}" ACTION="Create">\n'
        f"      <NAME>{name}</NAME>\n"
        f"      <PARENT>Indirect Expenses</PARENT>\n"
        f"      <ISGSTAPPLICABLE>Not Applicable</ISGSTAPPLICABLE>\n"
        f"      <ISBILLWISEON>No</ISBILLWISEON>\n"
        f"     </LEDGER>")


def _stock_item_xml(s, af: str) -> str:
    """Stock-item master in the TallyPrime Release 3.0+ GST schema.

    The HSN and GST rate are pinned AT THE ITEM LEVEL by the two
    ``SOURCEOF…DETAILS = Specify Details Here`` flags. These are the fields the
    item-alteration screen shows as "Source of details" — without them Tally
    3.0+ leaves the item on "As per Company/Stock Group" and silently drops the
    HSN/rate we supply, so the rate resolves to 0%. HSN now lives in its own
    HSNDETAILS.LIST and each rate row carries GSTRATEVALUATIONTYPE.
    """
    name = _e(s.name)

    # HSN pinned at the item level (only when we actually have an HSN/SAC).
    hsn_block = ""
    if s.hsn:
        hsn_block = (
            f"      <HSNDETAILS.LIST>\n"
            f"       <APPLICABLEFROM>{af}</APPLICABLEFROM>\n"
            f"       <HSNCODE>{_e(s.hsn)}</HSNCODE>\n"
            f"       <HSNDESCRIPTION>{name}</HSNDESCRIPTION>\n"
            f"       <SOURCEOFHSNDETAILS>Specify Details Here</SOURCEOFHSNDETAILS>\n"
            f"       <ISBLANKHSNDETAILS>No</ISBLANKHSNDETAILS>\n"
            f"      </HSNDETAILS.LIST>\n"
        )

    return (
        f'     <STOCKITEM NAME="{name}" ACTION="Create">\n'
        f"      <NAME>{name}</NAME>\n"
        f"      <PARENT>Primary</PARENT>\n"
        f"      <BASEUNITS>{_e(s.unit)}</BASEUNITS>\n"
        # The client's purchase and sales descriptions differ, so a sales
        # voucher regularly draws down an item that was never purchased under
        # that name. Tally rejects such a voucher outright unless the item
        # tolerates a negative balance, which is what this flag is.
        f"      <IGNORENEGATIVESTOCK>Yes</IGNORENEGATIVESTOCK>\n"
        f"      <GSTAPPLICABLE>Applicable</GSTAPPLICABLE>\n"
        f"      <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>\n"
        f"      <HSNCODE>{_e(s.hsn)}</HSNCODE>\n"
        f"{hsn_block}"
        f"      <GSTDETAILS.LIST>\n"
        f"       <APPLICABLEFROM>{af}</APPLICABLEFROM>\n"
        f"       <SOURCEOFGSTDETAILS>Specify Details Here</SOURCEOFGSTDETAILS>\n"
        f"       <TAXABILITY>{_e(s.taxability)}</TAXABILITY>\n"
        f"       <ISREVERSECHARGEAPPLICABLE>No</ISREVERSECHARGEAPPLICABLE>\n"
        f"       <ISNONGSTGOODS>No</ISNONGSTGOODS>\n"
        f"       <GSTCALCSLABONMRP>No</GSTCALCSLABONMRP>\n"
        f"{_rate_rows(s.gst_rate)}"
        f"      </GSTDETAILS.LIST>\n"
        f"     </STOCKITEM>")


# ---------------------------------------------------------------------------
# VOUCHERS
# ---------------------------------------------------------------------------
def build_vouchers_xml(invoices: List[Invoice]) -> str:
    parts = []
    for inv in invoices:
        if inv.direction not in ("purchase", "sale") or inv.has_errors:
            continue
        parts.append(_voucher_xml(inv))
    return _envelope("Vouchers", _messages(parts))


def _ledger_entry(name: str, amount: float, debit: bool,
                  bill_ref: Optional[str] = None, is_party: bool = False) -> str:
    """amount is always the positive magnitude.

    ``bill_ref`` adds the New Ref bill allocation. Party ledgers are created
    with ISBILLWISEON=Yes, and a bill-wise ledger posted without an allocation
    is an import exception, so the two have to move together.
    """
    sign = -abs(amount) if debit else abs(amount)
    bill = ""
    if bill_ref:
        bill = (
            "       <BILLALLOCATIONS.LIST>\n"
            f"        <NAME>{_e(bill_ref)}</NAME>\n"
            "        <BILLTYPE>New Ref</BILLTYPE>\n"
            f"        <AMOUNT>{sign:.2f}</AMOUNT>\n"
            "       </BILLALLOCATIONS.LIST>\n"
        )
    return (
        "      <LEDGERENTRIES.LIST>\n"
        f"       <LEDGERNAME>{_e(name)}</LEDGERNAME>\n"
        f"       <ISPARTYLEDGER>{'Yes' if is_party else 'No'}</ISPARTYLEDGER>\n"
        f"       <ISDEEMEDPOSITIVE>{'Yes' if debit else 'No'}</ISDEEMEDPOSITIVE>\n"
        f"       <AMOUNT>{sign:.2f}</AMOUNT>\n"
        f"{bill}"
        "      </LEDGERENTRIES.LIST>")


def _dec(v: float, places: int) -> str:
    """Fixed-point, never exponent notation, no trailing zero noise.

    "%g" flips to scientific notation past six significant digits, and Tally
    cannot parse "1.60401e+09" as either a quantity or a rate — the voucher
    carrying it fails the whole import.
    """
    s = f"{v:.{places}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _inventory_entry(inv, it, debit: bool) -> str:
    amt = it.taxable_value or 0
    sign = -abs(amt) if debit else abs(amt)
    # The line's own rate-specific nominal ledger; the invoice-level one is the
    # fallback for an item that never went through classify().
    ledger = it.ledger or inv.accounting_classification
    # The unit here must be the one the Unit/Stock Item masters were built with,
    # or the voucher fails with "Mismatch in Unit of Stock Items".
    unit = cfg.normalize_unit(it.unit)

    # Tally recomputes the line as RATE x BILLEDQTY, so the rate it is given has
    # to be the one that reproduces AMOUNT — otherwise the recomputed line no
    # longer matches the tax and party entries and the voucher is rejected as
    # out of balance. The printed rate is a gross rate on any row carrying a
    # discount column ("210.00 ... 40 %" against an amount of 15,750), so the
    # net rate is derived from the authoritative amount rather than exported as
    # printed. The discount itself is not lost — it stays on the Excel export.
    # The quantity is rounded to what the Unit master allows FIRST, and the rate
    # derived from that rounded figure — deriving it from the unrounded one puts
    # the product a few paise off the amount once Tally rounds the quantity.
    qty = rate = ""
    if it.quantity:
        q = round(it.quantity, cfg.UNIT_DECIMALS)
        qty = f"{_dec(q, cfg.UNIT_DECIMALS)} {unit}"
        rate = f"{_dec(abs(amt) / abs(q), 4)}/{unit}"
    return (
        "      <ALLINVENTORYENTRIES.LIST>\n"
        f"       <STOCKITEMNAME>{_e(it.description)}</STOCKITEMNAME>\n"
        f"       <ISDEEMEDPOSITIVE>{'Yes' if debit else 'No'}</ISDEEMEDPOSITIVE>\n"
        f"       <RATE>{_e(rate)}</RATE>\n"
        f"       <ACTUALQTY>{_e(qty)}</ACTUALQTY>\n"
        f"       <BILLEDQTY>{_e(qty)}</BILLEDQTY>\n"
        f"       <AMOUNT>{sign:.2f}</AMOUNT>\n"
        "       <ACCOUNTINGALLOCATIONS.LIST>\n"
        f"        <LEDGERNAME>{_e(ledger)}</LEDGERNAME>\n"
        f"        <ISDEEMEDPOSITIVE>{'Yes' if debit else 'No'}</ISDEEMEDPOSITIVE>\n"
        f"        <AMOUNT>{sign:.2f}</AMOUNT>\n"
        "       </ACCOUNTINGALLOCATIONS.LIST>\n"
        "      </ALLINVENTORYENTRIES.LIST>")


def _party_block(inv: Invoice, party: str) -> str:
    """The buyer/supplier attributes GSTR-1/3B needs.

    Reference doc §3.6: without these the voucher imports fine but the invoice
    is reported as "Uncertain" in the GST returns.
    """
    reg = (inv.party_registration_type or "Regular") if inv.party_gstin \
        else "Unregistered/Consumer"
    addr = (f'      <BASICBUYERADDRESS.LIST TYPE="String">\n'
            f"       <BASICBUYERADDRESS>{_e(inv.party_address)}</BASICBUYERADDRESS>\n"
            f"      </BASICBUYERADDRESS.LIST>\n") if inv.party_address else ""
    return (
        f"      <PARTYLEDGERNAME>{_e(party)}</PARTYLEDGERNAME>\n"
        f"      <PARTYNAME>{_e(party)}</PARTYNAME>\n"
        f"      <PARTYMAILINGNAME>{_e(party)}</PARTYMAILINGNAME>\n"
        f"      <BASICBUYERNAME>{_e(party)}</BASICBUYERNAME>\n"
        f"{addr}"
        f"      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>\n"
        f"      <STATENAME>{_e(inv.party_state)}</STATENAME>\n"
        f"      <PLACEOFSUPPLY>{_e(inv.place_of_supply)}</PLACEOFSUPPLY>\n"
        f"      <GSTREGISTRATIONTYPE>{_e(reg)}</GSTREGISTRATIONTYPE>\n"
        f"      <PARTYGSTIN>{_e(inv.party_gstin)}</PARTYGSTIN>\n"
        f"      <ISOTHTERRITORYASSESSEE>No</ISOTHTERRITORYASSESSEE>\n"
        f"      <ISBILLOFENTRYAVAILABLE>No</ISBILLOFENTRYAVAILABLE>\n"
        f"      <CONSIGNEEMAILINGNAME>{_e(party)}</CONSIGNEEMAILINGNAME>\n"
        f"      <CONSIGNEESTATENAME>{_e(inv.party_state)}</CONSIGNEESTATENAME>\n"
        f"      <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>\n"
        f"      <CONSIGNEEGSTIN>{_e(inv.party_gstin)}</CONSIGNEEGSTIN>\n"
        f"      <CONSIGNEEPINCODE>{_e(inv.party_pincode)}</CONSIGNEEPINCODE>\n"
    )


def _voucher_xml(inv: Invoice) -> str:
    is_purchase = inv.direction == "purchase"
    vt = cfg.VOUCHER_TYPE_PURCHASE if is_purchase else cfg.VOUCHER_TYPE_SALES
    date = _ymd(inv.invoice_date)
    party = inv.party_name or ("Sundry Creditor" if is_purchase else "Sundry Debtor")
    t = inv.tax
    lines: List[str] = []

    # party ledger: credit on purchase, debit on sale
    lines.append(_ledger_entry(party, inv.invoice_total, debit=not is_purchase,
                               bill_ref=inv.invoice_number or None, is_party=True))

    # taxes
    if is_purchase:
        for amt, led in ((t.cgst, cfg.LEDGER_INPUT_CGST), (t.sgst, cfg.LEDGER_INPUT_SGST),
                         (t.igst, cfg.LEDGER_INPUT_IGST)):
            if amt:
                lines.append(_ledger_entry(led, amt, debit=True))
    else:
        for amt, led in ((t.cgst, cfg.LEDGER_OUTPUT_CGST), (t.sgst, cfg.LEDGER_OUTPUT_SGST),
                         (t.igst, cfg.LEDGER_OUTPUT_IGST)):
            if amt:
                lines.append(_ledger_entry(led, amt, debit=False))

    # round off
    if t.round_off:
        ro = t.round_off
        # purchase: positive ro -> debit ; sale: positive ro -> credit
        debit = (ro > 0) if is_purchase else (ro < 0)
        lines.append(_ledger_entry(cfg.LEDGER_ROUND_OFF, abs(ro), debit=debit))

    # SOP 8 — Item (stock) mode carries inventory; Accounting (money-only) mode
    # posts the nominal ledger directly with no stock item or quantity.
    if inv.entry_mode == "item":
        # inventory (debit on purchase, credit on sale)
        for it in inv.items:
            lines.append(_inventory_entry(inv, it, debit=is_purchase))
        view = "Invoice Voucher View"
    else:
        lines.append(_ledger_entry(inv.accounting_classification,
                                   inv.taxable_total, debit=is_purchase))
        view = "Accounting Voucher View"

    # Stable external key back to the source document (reference doc §10.5).
    remote_id = uuid.uuid5(_NS, f"{COMPANY.gstin}|{vt}|{inv.invoice_number}|{date}")

    return (
        f'     <VOUCHER VCHTYPE="{_e(vt)}" ACTION="Create" OBJVIEW="{view}">\n'
        f"      <REMOTEID>{remote_id}</REMOTEID>\n"
        f"      <DATE>{date}</DATE>\n"
        f"      <EFFECTIVEDATE>{date}</EFFECTIVEDATE>\n"
        f"      <VOUCHERTYPENAME>{_e(vt)}</VOUCHERTYPENAME>\n"
        f"      <VOUCHERNUMBER>{_e(inv.invoice_number)}</VOUCHERNUMBER>\n"
        f"      <REFERENCE>{_e(inv.invoice_number)}</REFERENCE>\n"
        f"      <REFERENCEDATE>{date}</REFERENCEDATE>\n"
        f"{_party_block(inv, party)}"
        f"      <PERSISTEDVIEW>{view}</PERSISTEDVIEW>\n"
        f"      <ISINVOICE>Yes</ISINVOICE>\n"
        f"      <ISDELETED>No</ISDELETED>\n"
        f"      <ISCANCELLED>No</ISCANCELLED>\n"
        f"      <ISOPTIONAL>No</ISOPTIONAL>\n"
        + "\n".join(lines) + "\n"
        f"     </VOUCHER>"
    )
