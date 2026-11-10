"""Company configuration, GST state codes, and Tally ledger naming.

The "Company" here is the CA-office client whose books we are posting into.
Purchases = invoices where the Company is the *buyer*.
Sales     = invoices where the Company is the *seller*.

Everything is overridable via environment variables / the /config API so the
same tool can serve multiple clients.
"""
from __future__ import annotations

import calendar
import os
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Dict


# ---------------------------------------------------------------------------
# GST state code -> state name (TallyPrime expects the exact state name string)
# ---------------------------------------------------------------------------
STATE_CODES: Dict[str, str] = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman & Diu", "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra", "28": "Andhra Pradesh", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana",
    "37": "Andhra Pradesh", "38": "Ladakh", "97": "Other Territory",
}

STATE_NAME_TO_CODE: Dict[str, str] = {
    v.lower(): k for k, v in STATE_CODES.items()
}
# common spelling variants that appear on invoices
STATE_NAME_TO_CODE.update({
    "orissa": "21",
    "pondicherry": "34",
    "uttaranchal": "05",
    "chattisgarh": "22",
})


# ---------------------------------------------------------------------------
# Tally ledger names (exactly as the user specified, general practice)
# ---------------------------------------------------------------------------
LEDGER_INPUT_CGST = "Input CGST"
LEDGER_INPUT_SGST = "Input SGST"
LEDGER_INPUT_IGST = "Input IGST"
LEDGER_OUTPUT_CGST = "Output CGST"
LEDGER_OUTPUT_SGST = "Output SGST"
LEDGER_OUTPUT_IGST = "Output IGST"
LEDGER_ROUND_OFF = "Round Off"

# Purchase / Sales nominal ledgers keyed by integer GST rate (0 = exempt)
def purchase_ledger(rate: float) -> str:
    if not rate:
        return "Purchase exempted"
    return f"Purchase GST {fmt_rate(rate)}%"


def sales_ledger(rate: float) -> str:
    if not rate:
        return "Sales exempted"
    return f"Sales GST {fmt_rate(rate)}%"


def fmt_rate(rate: float) -> str:
    """5.0 -> '5', 12.5 -> '12.5'."""
    if float(rate).is_integer():
        return str(int(rate))
    return str(rate).rstrip("0").rstrip(".")


# All duty/tax ledgers and their Tally definitions (for master creation)
TAX_LEDGERS = {
    LEDGER_INPUT_CGST: ("CGST", "Duties & Taxes"),
    LEDGER_INPUT_SGST: ("SGST/UTGST", "Duties & Taxes"),
    LEDGER_INPUT_IGST: ("IGST", "Duties & Taxes"),
    LEDGER_OUTPUT_CGST: ("CGST", "Duties & Taxes"),
    LEDGER_OUTPUT_SGST: ("SGST/UTGST", "Duties & Taxes"),
    LEDGER_OUTPUT_IGST: ("IGST", "Duties & Taxes"),
}


@dataclass
class CompanyConfig:
    """The CA client whose books we post into."""
    name: str = os.environ.get("COMPANY_NAME", "Narsingh Prasad Bishnu Prasad")
    gstin: str = os.environ.get("COMPANY_GSTIN", "21AAAHN9743B1ZL")
    state_code: str = os.environ.get("COMPANY_STATE_CODE", "21")
    pan: str = os.environ.get("COMPANY_PAN", "AAAHN9743B")
    registration_type: str = os.environ.get("COMPANY_REG_TYPE", "Regular")
    address: str = os.environ.get("COMPANY_ADDRESS", "Main Road, Jharsuguda")
    pincode: str = os.environ.get("COMPANY_PINCODE", "768201")
    # SOP 6.4 — clients not maintaining inventory post money-only vouchers.
    stock_enabled: bool = os.environ.get("COMPANY_STOCK", "1") not in ("0", "false", "False")

    @property
    def state(self) -> str:
        return STATE_CODES.get(self.state_code, "")

    @property
    def country(self) -> str:
        return "India"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state
        d["country"] = self.country
        return d


# A single mutable instance the app uses; the /config endpoint can replace it.
COMPANY = CompanyConfig()


# ---------------------------------------------------------------------------
# Unit symbol -> formal name (GST UQC wording Tally expects on the Unit master)
# ---------------------------------------------------------------------------
UNIT_FORMAL_NAMES: Dict[str, str] = {
    "BAG": "BAGS", "BAL": "BALE", "BDL": "BUNDLES", "BKL": "BUCKLES",
    "BOU": "BILLION OF UNITS", "BOX": "BOX", "BTL": "BOTTLES",
    "BUN": "BUNCHES", "CAN": "CANS", "CBM": "CUBIC METERS",
    "CCM": "CUBIC CENTIMETERS", "CMS": "CENTIMETERS", "CTN": "CARTONS",
    "DOZ": "DOZENS", "DRM": "DRUMS", "GGK": "GREAT GROSS", "GMS": "GRAMMES",
    "GRS": "GROSS", "GYD": "GROSS YARDS", "KGS": "KILOGRAMS",
    "KLR": "KILOLITRE", "KME": "KILOMETRE", "LTR": "LITRES",
    "MLT": "MILILITRE", "MTR": "METERS", "MTS": "METRIC TON",
    "NOS": "NUMBERS", "OTH": "OTHERS", "PAC": "PACKS", "PCS": "PIECES",
    "PRS": "PAIRS", "QTL": "QUINTAL", "ROL": "ROLLS",
}

# symbols the parser emits that aren't UQC codes themselves
UNIT_ALIASES: Dict[str, str] = {
    "KG": "KGS", "GM": "GMS", "PKT": "PAC", "PAIR": "PRS", "ROLL": "ROL",
    "TON": "MTS", "SET": "NOS", "CASE": "BOX", "UNIT": "NOS",
}


DEFAULT_UNIT = "Nos"

# Decimal places on every Unit master. Tally rejects a voucher quantity with
# more decimals than its unit allows, and compound quantities ("134-400 k.g" ->
# 134.4) and derived rates both run to thousandths, so this is set at Tally's
# maximum rather than a tighter number the data can outgrow. Quantities are
# exported rounded to exactly this, so the two can never disagree.
UNIT_DECIMALS = 4


def normalize_unit(symbol: str) -> str:
    """The unit symbol used on BOTH the Unit master and the voucher line.

    The two have to agree exactly or Tally raises "Mismatch in Unit of Stock
    Items" on the voucher pass, so every caller must go through here rather than
    reading ``item.unit`` directly.

    Known symbols collapse onto their GST UQC code ("Kg" and "KGS" are one
    master, not two); anything unrecognised is passed through as written.
    """
    raw = (symbol or "").strip()
    if not raw:
        return DEFAULT_UNIT
    key = UNIT_ALIASES.get(raw.upper(), raw.upper())
    return key.title() if key in UNIT_FORMAL_NAMES else raw


def unit_uqc(symbol: str) -> str:
    """The GST Unit Quantity Code Tally pins on a Unit master, "PAC-PACKS".

    TallyPrime 3.x asks for this on the Unit Creation screen ("Unit Quantity
    Code (UQC)") and a unit imported without one is left incomplete — the stock
    items built on it then have nothing to report quantities in, so the unit
    does not resolve and vouchers naming it fail with "Referenced master is
    missing".

    UNIT_FORMAL_NAMES is already the UQC table (the GST codes and their
    wording), so the code is just its two halves joined. Anything not on that
    list is OTH-OTHERS, which is the code the portal itself uses for units it
    does not recognise.
    """
    key = normalize_unit(symbol).upper()
    key = UNIT_ALIASES.get(key, key)
    formal = UNIT_FORMAL_NAMES.get(key)
    return f"{key}-{formal}" if formal else "OTH-OTHERS"


def unit_formal_name(symbol: str) -> str:
    """Formal name for a unit symbol, or "" when there isn't a distinct one.

    Tally rejects a Unit master whose Formal Name equals its Symbol ("Formal
    name and Symbol are the same"), and a blank formal name is always accepted —
    so anything we can't expand is deliberately left empty rather than echoed.
    """
    key = normalize_unit(symbol).upper()
    key = UNIT_ALIASES.get(key, key)
    formal = UNIT_FORMAL_NAMES.get(key, "")
    return "" if formal.upper() == normalize_unit(symbol).upper() else formal


def end_of_current_month() -> str:
    """Last day of the month this export is generated in, as an ISO date.

    The exporters' last-resort voucher date, for an invoice whose own date
    could not be read at all — Tally rejects a voucher with no date outright.
    A voucher normally carries the date printed on the invoice, unchanged, and
    an unreadable date is an error-level exception that keeps the invoice out
    of the export entirely, so this is a backstop rather than a default.

    The dated master blocks do NOT use this — they use fy_start(), because this
    tracks TODAY and would date a back-dated batch's rate block after its own
    vouchers, which Tally silently resolves to 0%.
    """
    today = date.today()
    return today.replace(day=calendar.monthrange(today.year, today.month)[1]).isoformat()


def fy_start(iso: str = "") -> str:
    """1 April of the Indian financial year the given date falls in, as ISO.

    Every dated master block (GST Applicability, GST Rate, HSN/SAC, GST
    Registration) is stamped with this rather than with a date taken from the
    invoice or from today. Two reasons:

      * Tally resolves a rate block dated AFTER the voucher to 0%, silently. An
        FY-start is on or before every voucher of that year, so a back-dated
        batch imported later in the year still picks its rate up.
      * GST rates and HSN codes are notified per financial year, so 1 April is
        the date a CA would key by hand — and re-importing next year's batch
        adds a second block from the next 1 April instead of overwriting this
        one's history.

    An unreadable/blank date falls back to the FY containing today.
    """
    try:
        d = date.fromisoformat((iso or "")[:10])
    except ValueError:
        d = date.today()
    return date(d.year if d.month >= 4 else d.year - 1, 4, 1).isoformat()


# Tally voucher type names (defaults — Purchase / Sales accounting vouchers)
VOUCHER_TYPE_PURCHASE = os.environ.get("VT_PURCHASE", "Purchase")
VOUCHER_TYPE_SALES = os.environ.get("VT_SALES", "Sales")
