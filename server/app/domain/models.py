"""Pydantic models for the extracted-invoice domain."""
from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = ""
    hsn_sac: str = ""
    quantity: Optional[float] = None
    unit: str = ""
    rate: Optional[float] = None
    disc_pct: Optional[float] = None
    taxable_value: Optional[float] = None
    gst_rate: Optional[float] = None          # combined % (e.g. 18)
    amount: Optional[float] = None            # taxable value for the line
    # Nominal ledger this line posts to, chosen from ITS OWN gst_rate so a
    # mixed-rate invoice splits across "Sales GST 18%" / "Sales GST 5%" /
    # "Sales exempted" instead of forcing every line into the dominant one.
    ledger: str = ""


class Assumption(BaseModel):
    field: str
    value: str
    reason: str


class Exception_(BaseModel):
    code: str                                 # e.g. INVALID_GSTIN
    severity: Literal["error", "warning", "info"]
    message: str


class TaxBreakup(BaseModel):
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    cess: float = 0.0
    round_off: float = 0.0


class JournalLine(BaseModel):
    ledger: str
    debit: float = 0.0
    credit: float = 0.0


class Invoice(BaseModel):
    # --- provenance ---
    source_file: str = ""
    # 'google-vision' | 'google-vision + pdf-text-layer' | 'gstr2a-excel'
    ocr_engine: str = ""
    raw_text: str = ""
    source: Literal["invoice", "gstr2a"] = "invoice"   # SOP 8, decision-rule input

    # --- classification ---
    direction: Literal["purchase", "sale", "unknown"] = "unknown"
    nature_of_transaction: Literal["intra-state", "inter-state", "unknown"] = "unknown"
    accounting_classification: str = ""       # e.g. "Purchase GST 18%"
    # SOP 8 — Item (stock) invoice vs Accounting (money-only) invoice
    entry_mode: Literal["item", "accounting"] = "item"

    # --- the counterparty (supplier for purchase, customer for sale) ---
    party_name: str = ""
    party_gstin: str = ""
    party_state_code: str = ""
    party_state: str = ""
    party_address: str = ""
    party_pincode: str = ""
    party_registration_type: str = "Regular"

    # --- invoice header ---
    invoice_number: str = ""
    invoice_date: str = ""                    # normalised YYYY-MM-DD
    invoice_date_display: str = ""            # DD-MMM-YYYY for Tally
    place_of_supply: str = ""
    place_of_supply_code: str = ""

    # --- line items & totals ---
    items: List[LineItem] = Field(default_factory=list)
    taxable_total: float = 0.0
    tax: TaxBreakup = Field(default_factory=TaxBreakup)
    # Tax heads as *printed* on the invoice. Kept alongside the computed `tax`
    # so SOP 10 "wrong tax head" / GST-mismatch can be detected. Never used for
    # posting — `tax` stays authoritative so vouchers always balance.
    printed_tax: Optional[TaxBreakup] = None
    invoice_total: float = 0.0
    dominant_gst_rate: Optional[float] = None

    # --- derived accounting artefacts ---
    journal: List[JournalLine] = Field(default_factory=list)
    itc_eligible: Optional[bool] = None
    itc_remarks: str = ""

    # --- QA ---
    assumptions: List[Assumption] = Field(default_factory=list)
    exceptions: List[Exception_] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(e.severity == "error" for e in self.exceptions)
