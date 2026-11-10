"""Derive the set of Tally masters (ledgers, stock items, units) required by a
batch of invoices, deduplicated and ready for export.

GST rate is carried on the stock item master (per the user's requirement) and
the right tax / nominal ledgers are created so vouchers import cleanly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from . import config as cfg
from .config import COMPANY
from shared.models import Invoice


@dataclass
class PartyLedger:
    name: str
    parent: str               # Sundry Creditors / Sundry Debtors
    gstin: str
    reg_type: str
    state: str
    pincode: str
    address: str
    place_of_supply: str


@dataclass
class NominalLedger:
    name: str
    parent: str               # Purchase Accounts / Sales Accounts
    taxability: str           # Taxable / Exempt
    gst_rate: float
    is_sales: bool
    # True when any voucher posts to this ledger money-only. Such vouchers carry
    # no stock item, so the taxability/rate has to live on the ledger master
    # itself or Tally rejects the import with "Taxability Type is invalid".
    money_only: bool = False


@dataclass
class TaxLedger:
    name: str
    tax_type: str             # CGST / SGST/UTGST / IGST


@dataclass
class StockItem:
    name: str
    hsn: str
    unit: str
    gst_rate: float
    taxability: str


@dataclass
class MasterSet:
    parties: Dict[str, PartyLedger] = field(default_factory=dict)
    nominals: Dict[str, NominalLedger] = field(default_factory=dict)
    taxes: Dict[str, TaxLedger] = field(default_factory=dict)
    stock_items: Dict[str, StockItem] = field(default_factory=dict)
    units: Dict[str, None] = field(default_factory=dict)
    need_round_off: bool = False
    # 1 April of the financial year the batch's EARLIEST invoice falls in — see
    # cfg.fy_start(). Every dated master block (GST applicability, GST rate,
    # HSN/SAC, GST registration) hangs off it, so no block is ever dated after
    # a voucher that needs it, which is what makes Tally resolve a rate to 0%.
    applicable_from: str = ""


def _taxability(rate: float) -> str:
    return "Taxable" if rate else "Exempt"


def registration_type(inv: Invoice) -> str:
    """Party's GST registration type, as both the ledger master and the voucher
    must state it — a voucher disagreeing with its own party ledger imports as
    a GST-registration exception."""
    if not inv.party_gstin:
        return "Unregistered/Consumer"
    return inv.party_registration_type or "Regular"


def _batch_fy_start(invoices: List[Invoice]) -> str:
    dates = [inv.invoice_date for inv in invoices
             if inv.direction in ("purchase", "sale") and inv.invoice_date]
    return cfg.fy_start(min(dates) if dates else "")


def collect_masters(invoices: List[Invoice]) -> MasterSet:
    ms = MasterSet()
    ms.applicable_from = _batch_fy_start(invoices)

    for inv in invoices:
        if inv.direction not in ("purchase", "sale"):
            continue

        # --- party ledger ---
        if inv.party_name:
            parent = ("Sundry Creditors" if inv.direction == "purchase"
                      else "Sundry Debtors")
            reg = registration_type(inv)
            ms.parties.setdefault(inv.party_name, PartyLedger(
                name=inv.party_name, parent=parent, gstin=inv.party_gstin,
                reg_type=reg, state=inv.party_state, pincode=inv.party_pincode,
                address=inv.party_address,
                place_of_supply=inv.place_of_supply or COMPANY.state))

        # --- nominal (purchase/sales) ledgers ---
        # An item invoice needs one ledger per rate present on the invoice, not
        # just the dominant one; a money-only voucher needs only the summary
        # ledger, because that is the single line it posts.
        parent = "Sales Accounts" if inv.direction == "sale" else "Purchase Accounts"
        wanted = []
        if inv.entry_mode == "item":
            wanted = [(it.ledger, it.gst_rate or 0) for it in inv.items if it.ledger]
        if not wanted:
            wanted = [(inv.accounting_classification, inv.dominant_gst_rate or 0)]
        for name, rate in wanted:
            if not name or name == "Suspense":
                continue
            nominal = ms.nominals.setdefault(name, NominalLedger(
                name=name, parent=parent,
                taxability=_taxability(rate), gst_rate=rate,
                is_sales=(inv.direction == "sale")))
            if inv.entry_mode != "item":
                nominal.money_only = True

        # --- tax ledgers actually used ---
        t = inv.tax
        if inv.direction == "purchase":
            if t.cgst:
                ms.taxes.setdefault(cfg.LEDGER_INPUT_CGST, TaxLedger(cfg.LEDGER_INPUT_CGST, "CGST"))
            if t.sgst:
                ms.taxes.setdefault(cfg.LEDGER_INPUT_SGST, TaxLedger(cfg.LEDGER_INPUT_SGST, "SGST/UTGST"))
            if t.igst:
                ms.taxes.setdefault(cfg.LEDGER_INPUT_IGST, TaxLedger(cfg.LEDGER_INPUT_IGST, "IGST"))
        else:
            if t.cgst:
                ms.taxes.setdefault(cfg.LEDGER_OUTPUT_CGST, TaxLedger(cfg.LEDGER_OUTPUT_CGST, "CGST"))
            if t.sgst:
                ms.taxes.setdefault(cfg.LEDGER_OUTPUT_SGST, TaxLedger(cfg.LEDGER_OUTPUT_SGST, "SGST/UTGST"))
            if t.igst:
                ms.taxes.setdefault(cfg.LEDGER_OUTPUT_IGST, TaxLedger(cfg.LEDGER_OUTPUT_IGST, "IGST"))

        if t.round_off:
            ms.need_round_off = True

        # --- stock items + units (GST rate carried on the item) ---
        # Money-only vouchers reference no stock item, so creating the masters
        # would import inventory the client does not maintain (SOP 6.4 / 8).
        if inv.entry_mode != "item":
            continue
        for it in inv.items:
            if not it.description:
                continue
            key = it.description
            rate = it.gst_rate if it.gst_rate is not None else (inv.dominant_gst_rate or 0)
            unit = cfg.normalize_unit(it.unit)
            ms.stock_items.setdefault(key, StockItem(
                name=it.description, hsn=it.hsn_sac, unit=unit,
                gst_rate=rate or 0, taxability=_taxability(rate or 0)))
            ms.units.setdefault(unit, None)
    return ms
