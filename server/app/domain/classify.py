"""Turn a parsed Invoice into accounting-ready, Tally-safe output.

Responsibilities:
  * Determine nature of transaction (intra/inter-state) from state codes.
  * Compute CGST/SGST/IGST from taxable values per GST-rate bucket
    (CA-correct & internally consistent -> avoids Tally GST-mismatch errors).
  * Pick the right purchase/sales nominal ledger and tax ledgers.
  * Build the journal entry.
  * Assess ITC eligibility.
  * Raise exceptions for every defect Tally would reject on import.
"""
from __future__ import annotations

from collections import defaultdict

from . import config as cfg
from .config import COMPANY
from .models import Invoice, JournalLine, Exception_, Assumption
from .tax_heads import TAX_HEAD_RES
# MIGRATION(A2/A5): hsn_rate_map is a reading-side function that lives with the
# parser in the OCR service (moved in A3). classify re-parses inv.raw_text with
# it — kept as-is per the faithful migration (Option A). The import path below is
# finalised when in-process packaging is wired in A5; tracked as tech debt to be
# removed later by carrying the HSN rate map on the reading contract
# (see docs: principle P4 / ADR-0010).
from reading.parser import hsn_rate_map
from .validate import validate_gstin, validate_place_of_supply

# HSN/SAC chapters whose ITC is blocked under sec.17(5) (illustrative subset)
BLOCKED_ITC_HSN_PREFIX = ("8703",)  # motor vehicles for personal use, etc.


def classify(inv: Invoice) -> Invoice:
    _validate_company(inv)
    _total_from_items(inv)
    _infer_place_of_supply(inv)
    _determine_nature(inv)
    _fill_missing_rates(inv)
    _compute_taxes(inv)
    _determine_entry_mode(inv)
    _dominant_rate(inv)
    _set_classification(inv)
    _reconcile(inv)
    _check_tax_heads(inv)
    _build_journal(inv)
    _assess_itc(inv)
    _validate_party_and_pos(inv)
    return inv


# ---------------------------------------------------------------------------
def _total_from_items(inv: Invoice):
    """The taxable total is the lines, always.

    It is derived here rather than trusted from whoever set it, because the
    lines can change after they were first summed — a CA editing a quantity in
    the UI, or the Gemini reader replacing the parser's rows with its own. A
    stale total silently disagrees with the tax computed from the lines, and
    the invoice reports a TOTAL_MISMATCH against itself.
    """
    if inv.items:
        inv.taxable_total = round(sum(i.taxable_value or 0 for i in inv.items), 2)


def _infer_place_of_supply(inv: Invoice):
    """Fill an unprinted place of supply from the parties (SOP 5).

    Derived here, not in the parser, because it depends on the party's state
    code — which may only be known *after* the parse (an unregistered buyer's
    code is printed as text, and the Gemini reader is what picks it up) and can
    change when a CA corrects a GSTIN in the UI. Left in the parser it was
    computed once, against a blank, and never revisited.
    """
    if inv.place_of_supply or inv.place_of_supply_code:
        return
    if inv.direction == "sale" and inv.party_state_code:
        code, why = inv.party_state_code, "buyer's state for an outward supply"
    elif inv.direction == "purchase" and COMPANY.state_code:
        code, why = COMPANY.state_code, "company's state for an inward supply"
    else:
        return
    inv.place_of_supply_code = code
    inv.place_of_supply = cfg.STATE_CODES.get(code, "")
    inv.assumptions.append(Assumption(
        field="place_of_supply", value=inv.place_of_supply,
        reason=f"Not printed on the invoice; inferred as the {why}."))


def _validate_company(inv: Invoice):
    ok, reason = validate_gstin(COMPANY.gstin)
    if not ok:
        inv.exceptions.append(Exception_(
            code="COMPANY_GST_INVALID", severity="error",
            message=f"GST Registration Details of the Company are invalid: {reason}. "
                    f"Set a valid Company GSTIN in configuration before import."))
    if not COMPANY.registration_type:
        inv.exceptions.append(Exception_(
            code="COMPANY_REG_TYPE_MISSING", severity="error",
            message="Company GST Registration Type is not specified."))


def _determine_nature(inv: Invoice):
    if inv.direction == "sale":
        supplier_sc, recipient_sc = COMPANY.state_code, inv.party_state_code
    elif inv.direction == "purchase":
        supplier_sc, recipient_sc = inv.party_state_code, COMPANY.state_code
    else:
        inv.nature_of_transaction = "unknown"
        return

    if supplier_sc and recipient_sc:
        inv.nature_of_transaction = (
            "intra-state" if supplier_sc == recipient_sc else "inter-state")
    else:
        # fall back to comparing place of supply with company state
        if inv.place_of_supply_code and COMPANY.state_code:
            inv.nature_of_transaction = (
                "intra-state" if inv.place_of_supply_code == COMPANY.state_code
                else "inter-state")
        else:
            inv.nature_of_transaction = "unknown"


def _fill_missing_rates(inv: Invoice):
    """Back-fill the per-line GST rate for templates that don't print one.

    TallyPrime's own invoice print has no GST-rate column on the item rows at
    all; the rates live only in the HSN/SAC tax summary at the foot. That
    summary is per-HSN, so it is tried first — it is the only source that keeps
    a mixed-rate invoice (18% pipe next to 5% rope and a 0% shovel) correct. A
    single invoice-level rate is the fallback for everything else.
    """
    missing = [it for it in inv.items if it.gst_rate is None]
    if not missing:
        _check_summary_rates(inv)
        return

    by_hsn = hsn_rate_map(inv.raw_text)
    for it in list(missing):
        rate = by_hsn.get(it.hsn_sac)
        if rate is None:
            continue
        it.gst_rate = rate
        missing.remove(it)
        inv.assumptions.append(Assumption(
            field=f"gst_rate[{it.description[:24]}]", value=f"{cfg.fmt_rate(rate)}%",
            reason=f"This template prints no per-line GST rate; taken from the "
                   f"HSN/SAC tax summary row for HSN {it.hsn_sac}."))

    if not missing:
        _check_summary_rates(inv)
        return

    rate = _printed_invoice_rate(inv)
    if rate is None:
        return
    for it in missing:
        it.gst_rate = rate
        inv.assumptions.append(Assumption(
            field=f"gst_rate[{it.description[:24]}]", value=f"{cfg.fmt_rate(rate)}%",
            reason="Per-line GST rate not printed; taken from the invoice-level "
                   "GST rate / tax summary."))
    _check_summary_rates(inv)


def _check_summary_rates(inv: Invoice):
    """Line rate vs the HSN summary — a disagreement means one of them is wrong.

    The line rate is kept (it is what the CA sees and edits in the UI); this
    only surfaces the conflict, because posting the wrong rate is exactly what
    puts an invoice into GSTR "Uncertain".
    """
    by_hsn = hsn_rate_map(inv.raw_text)
    if not by_hsn:
        return
    for it in inv.items:
        summary = by_hsn.get(it.hsn_sac)
        if summary is None or it.gst_rate is None:
            continue
        if abs(it.gst_rate - summary) > 0.01:
            inv.exceptions.append(Exception_(
                code="GST_RATE_MISMATCH", severity="warning",
                message=f"Line '{it.description[:28]}' is charged at "
                        f"{cfg.fmt_rate(it.gst_rate)}% but the HSN/SAC summary "
                        f"shows {cfg.fmt_rate(summary)}% for HSN {it.hsn_sac}. "
                        f"The line rate was used; verify the invoice."))


def _printed_invoice_rate(inv: Invoice):
    """The one GST rate printed on the invoice, as a COMBINED percentage.

    CGST and SGST are each printed at half the supply's rate ("Cgst 9%" plus
    "9% Sgst" is an 18% supply), so the two heads are added; IGST is printed
    whole. Reading either half as the whole rate halves every voucher's tax,
    which is silent and only shows up as a GSTR mismatch months later.
    """
    import re

    seen: dict = {}
    for ln in (inv.raw_text or "").splitlines():
        heads = [k for k, rx in TAX_HEAD_RES.items() if rx.search(ln)]
        if len(heads) != 1 or heads[0] in seen:
            continue                       # a multi-head line is a table header
        pcts = [float(p) for p in re.findall(r"(\d{1,2}(?:\.\d+)?)\s*%", ln)]
        pcts = [p for p in pcts if 0 < p <= 28]
        if pcts:
            seen[heads[0]] = max(pcts)     # "Cgst 9%   9 %   205.20" repeats it

    if "igst" in seen:
        return seen["igst"]
    if "cgst" in seen and "sgst" in seen:
        return round(seen["cgst"] + seen["sgst"], 2) or None
    if "cgst" in seen or "sgst" in seen:
        # only one half printed (or only one read) — it is still a half
        return round(seen.get("cgst") or seen.get("sgst"), 2) * 2 or None

    m = re.search(r"%\s*(\d{1,2}(?:\.\d+)?)\b", inv.raw_text or "")  # "% 18"
    if m and 0 < float(m.group(1)) <= 28:
        return float(m.group(1))
    return None


def _compute_taxes(inv: Invoice):
    """Compute tax PER LINE (matches how invoices are printed) so the totals
    reconcile to the paisa and Tally never flags a GST mismatch. CGST==SGST and
    IGST==taxable*rate by construction."""
    cgst = sgst = igst = 0.0
    for it in inv.items:
        rate = it.gst_rate or 0
        taxable = it.taxable_value or 0
        if inv.nature_of_transaction == "inter-state":
            igst += round(taxable * rate / 100.0, 2)
        else:  # intra-state default; split equally
            half = round(taxable * rate / 200.0, 2)
            cgst += half
            sgst += half
    inv.tax.cgst = round(cgst, 2)
    inv.tax.sgst = round(sgst, 2)
    inv.tax.igst = round(igst, 2)


def _determine_entry_mode(inv: Invoice):
    """SOP 8 decision rule.

        source = GSTR-2A            -> Accounting (2A carries no HSN/stock detail)
        client stock flag Disabled  -> Accounting
        otherwise                   -> Item (stock) invoice

    Item mode additionally requires that item/quantity detail actually exists;
    an invoice whose table could not be read falls back to money-only so the
    voucher still posts rather than emitting empty inventory entries.
    """
    if inv.source == "gstr2a":
        inv.entry_mode = "accounting"
        return
    if not COMPANY.stock_enabled:
        inv.entry_mode = "accounting"
        return
    if not inv.items:
        inv.entry_mode = "accounting"
        inv.assumptions.append(Assumption(
            field="entry_mode", value="accounting",
            reason="Stock is enabled but no item/HSN/quantity detail could be read "
                   "from the invoice; posted as a money-only voucher."))
        return
    inv.entry_mode = "item"


def _check_tax_heads(inv: Invoice):
    """SOP 10 — 'wrong tax head' and 'GST mismatch'.

    Compares the tax heads *printed* on the invoice against what the nature of
    transaction requires. The computed `inv.tax` remains authoritative for
    posting (it is correct by construction), so these are warnings that tell the
    CA the source document itself is wrong.
    """
    p = inv.printed_tax
    if p is None:
        return

    printed_igst = round(p.igst, 2)
    printed_cs = round(p.cgst + p.sgst, 2)

    if inv.nature_of_transaction == "intra-state" and printed_igst > 0:
        inv.exceptions.append(Exception_(
            code="WRONG_TAX_HEAD", severity="warning",
            message=f"Invoice charges IGST {printed_igst} on an intra-state supply "
                    f"(place of supply {inv.place_of_supply or '?'} matches the "
                    f"company state). Corrected to CGST {inv.tax.cgst} + SGST "
                    f"{inv.tax.sgst} for posting; verify with the supplier."))
    elif inv.nature_of_transaction == "inter-state" and printed_cs > 0:
        inv.exceptions.append(Exception_(
            code="WRONG_TAX_HEAD", severity="warning",
            message=f"Invoice charges CGST/SGST {printed_cs} on an inter-state "
                    f"supply (place of supply {inv.place_of_supply or '?'}). "
                    f"Corrected to IGST {inv.tax.igst} for posting; verify with "
                    f"the supplier."))

    # GST mismatch — printed total tax vs taxable x rate.
    printed_total = round(printed_igst + printed_cs, 2)
    computed_total = round(inv.tax.cgst + inv.tax.sgst + inv.tax.igst, 2)
    if printed_total and abs(printed_total - computed_total) > 1.0:
        inv.exceptions.append(Exception_(
            code="GST_MISMATCH", severity="warning",
            message=f"Printed GST {printed_total} differs from taxable x rate "
                    f"{computed_total} by {round(printed_total - computed_total, 2)}. "
                    f"Computed value used; verify rates and taxable values."))


def _set_classification(inv: Invoice):
    rate = _pick_dominant_rate(inv)
    if inv.direction == "purchase":
        inv.accounting_classification = cfg.purchase_ledger(rate)
    elif inv.direction == "sale":
        inv.accounting_classification = cfg.sales_ledger(rate)
    else:
        inv.accounting_classification = "Suspense"
        for it in inv.items:
            it.ledger = ""
        return

    # One invoice can mix rates — 18% pipe, 5% rope and a 0% shovel on the same
    # bill. Each line posts to the nominal ledger for ITS OWN rate so the sales
    # register splits by rate the way GSTR-1 expects, and so a 0% line never
    # lands in a "Sales GST 18%" ledger. accounting_classification stays the
    # invoice-level summary, and is what a money-only voucher posts to.
    pick = cfg.purchase_ledger if inv.direction == "purchase" else cfg.sales_ledger
    for it in inv.items:
        it.ledger = pick(it.gst_rate or 0)


def _pick_dominant_rate(inv: Invoice) -> float:
    weights = defaultdict(float)
    for it in inv.items:
        weights[it.gst_rate or 0] += it.taxable_value or 0
    if not weights:
        return 0.0
    return max(weights, key=weights.get)


def _dominant_rate(inv: Invoice):
    inv.dominant_gst_rate = _pick_dominant_rate(inv)


# ---------------------------------------------------------------------------
def _build_journal(inv: Invoice):
    """Build a guaranteed-balanced double entry. The Round Off ledger takes the
    exact balancing figure so debits == credits to the paisa."""
    t = inv.tax
    j = inv.journal
    total = inv.invoice_total

    if inv.direction == "purchase":
        j.append(JournalLine(ledger=inv.accounting_classification, debit=inv.taxable_total))
        if t.igst:
            j.append(JournalLine(ledger=cfg.LEDGER_INPUT_IGST, debit=t.igst))
        if t.cgst:
            j.append(JournalLine(ledger=cfg.LEDGER_INPUT_CGST, debit=t.cgst))
        if t.sgst:
            j.append(JournalLine(ledger=cfg.LEDGER_INPUT_SGST, debit=t.sgst))
        bal = round(total - (inv.taxable_total + t.cgst + t.sgst + t.igst), 2)
        _add_round_off(j, bal)
        j.append(JournalLine(ledger=inv.party_name or "Sundry Creditor", credit=total))

    elif inv.direction == "sale":
        j.append(JournalLine(ledger=inv.party_name or "Sundry Debtor", debit=total))
        j.append(JournalLine(ledger=inv.accounting_classification, credit=inv.taxable_total))
        if t.igst:
            j.append(JournalLine(ledger=cfg.LEDGER_OUTPUT_IGST, credit=t.igst))
        if t.cgst:
            j.append(JournalLine(ledger=cfg.LEDGER_OUTPUT_CGST, credit=t.cgst))
        if t.sgst:
            j.append(JournalLine(ledger=cfg.LEDGER_OUTPUT_SGST, credit=t.sgst))
        bal = round(total - (inv.taxable_total + t.cgst + t.sgst + t.igst), 2)
        # on a sale the round off sits opposite the expense side
        _add_round_off(j, bal, credit_side=True)


def _add_round_off(j, bal: float, credit_side: bool = False):
    if not bal:
        return
    # `bal` must land on the debit side for purchases, credit side for sales,
    # so total debits == total credits. A negative bal flips to the other side.
    if credit_side:
        if bal > 0:
            j.append(JournalLine(ledger=cfg.LEDGER_ROUND_OFF, credit=bal))
        else:
            j.append(JournalLine(ledger=cfg.LEDGER_ROUND_OFF, debit=-bal))
    else:
        if bal > 0:
            j.append(JournalLine(ledger=cfg.LEDGER_ROUND_OFF, debit=bal))
        else:
            j.append(JournalLine(ledger=cfg.LEDGER_ROUND_OFF, credit=-bal))


# ---------------------------------------------------------------------------
def _assess_itc(inv: Invoice):
    if inv.direction != "purchase":
        inv.itc_eligible = None
        inv.itc_remarks = "ITC not applicable on outward supply."
        return
    blocked = [it for it in inv.items
               if it.hsn_sac and it.hsn_sac.startswith(BLOCKED_ITC_HSN_PREFIX)]
    ok, reason = validate_gstin(inv.party_gstin)
    if not ok:
        inv.itc_eligible = False
        inv.itc_remarks = f"ITC at risk: supplier GSTIN invalid ({reason})."
    elif blocked:
        inv.itc_eligible = False
        inv.itc_remarks = ("ITC blocked u/s 17(5) for items: "
                           + ", ".join(b.description for b in blocked))
        inv.exceptions.append(Exception_(
            code="BLOCKED_ITC", severity="warning",
            message=inv.itc_remarks))
    elif inv.party_registration_type.lower() == "composition":
        inv.itc_eligible = False
        inv.itc_remarks = "ITC not available: supplier is under Composition scheme."
    else:
        inv.itc_eligible = True
        inv.itc_remarks = ("Eligible for ITC, subject to GSTR-2B reflection and "
                           "sec.16 conditions (payment within 180 days, goods received).")


# ---------------------------------------------------------------------------
def _validate_party_and_pos(inv: Invoice):
    label = "Supplier" if inv.direction == "purchase" else "Consignee/Buyer"
    ok, reason = validate_gstin(inv.party_gstin)
    if not ok:
        sev = "error" if inv.party_gstin else "warning"
        inv.exceptions.append(Exception_(
            code="INVALID_PARTY_GSTIN", severity=sev,
            message=f"Invalid {label} GSTIN: {reason}."
                    + ("" if inv.party_gstin else
                       " (Unregistered party — set Registration Type to "
                       "'Unregistered/Consumer' to import.)")))
        if not inv.party_gstin:
            inv.party_registration_type = "Unregistered/Consumer"

    ok, reason = validate_place_of_supply(inv.place_of_supply, inv.place_of_supply_code)
    if not ok:
        inv.exceptions.append(Exception_(
            code="INVALID_PLACE_OF_SUPPLY", severity="error",
            message=f"Place of Supply is invalid or not specified: {reason}."))

    if inv.nature_of_transaction == "unknown":
        inv.exceptions.append(Exception_(
            code="TAXABILITY_UNDETERMINED", severity="error",
            message="Taxability Type / nature of transaction could not be "
                    "determined (missing state codes). Set Place of Supply & "
                    "party state before import."))

    if not inv.invoice_number:
        inv.exceptions.append(Exception_(
            code="MISSING_INVOICE_NUMBER", severity="error",
            message="Invoice / Voucher Number is missing."))
    if not inv.invoice_date:
        inv.exceptions.append(Exception_(
            code="MISSING_INVOICE_DATE", severity="error",
            message="Invoice / Voucher Date is missing or unpar. "))

    if not inv.items:
        inv.exceptions.append(Exception_(
            code="NO_LINE_ITEMS", severity="warning",
            message="No line items were detected; review the invoice manually."))

    # The client buys and sells under different item descriptions, so a sale
    # routinely hits a stock item with no purchase behind it. Tally REFUSES the
    # voucher when the item disallows negative balances, so the stock masters
    # are created with negative balances allowed (IGNORENEGATIVESTOCK) — this
    # note is here so a negative closing stock reads as expected, not as a
    # failed import.
    if inv.direction == "sale" and inv.entry_mode == "item" and inv.items:
        inv.exceptions.append(Exception_(
            code="NEGATIVE_STOCK_POSSIBLE", severity="info",
            message="Outward item invoice: if these items were purchased under "
                    "different descriptions, stock will go negative in Tally. The "
                    "stock masters allow negative balances so the voucher still "
                    "imports; map the sales items to their purchase items in Tally "
                    "if the quantity balance has to be meaningful."))

    # Tally import reference §3.6: the twelve buyer/supplier attributes. A gap
    # here does not stop the voucher importing, so this is a warning — but the
    # invoice lands in GSTR-1/3B as "Uncertain" until it is filled in.
    gaps = [lbl for lbl, val in (("Address", inv.party_address),
                                 ("Pincode", inv.party_pincode),
                                 ("State", inv.party_state)) if not val]
    if gaps:
        inv.exceptions.append(Exception_(
            code="INCOMPLETE_GSTR_PARTY_DETAILS", severity="warning",
            message=f"{label} {', '.join(gaps)} not found on the invoice. The "
                    f"voucher will import, but GSTR-1/3B will report it as "
                    f"Uncertain until this is filled in."))


def _reconcile(inv: Invoice):
    """Make the computed total authoritative (guarantees a balanced voucher),
    derive round-off, and warn if the printed grand total disagrees."""
    base = round(inv.taxable_total + inv.tax.cgst + inv.tax.sgst + inv.tax.igst, 2)
    printed = inv.invoice_total  # parsed grand total (may be noisy)

    if printed:
        diff = round(printed - base, 2)
        if abs(diff) < 1.0:
            # the small gap is the invoice's round-off
            inv.tax.round_off = diff
        else:
            inv.exceptions.append(Exception_(
                code="TOTAL_MISMATCH", severity="warning",
                message=f"Printed invoice total {printed} differs from computed "
                        f"taxable+GST {base} by {diff}. Round-off kept as "
                        f"{inv.tax.round_off}; verify quantities/rates."))
    elif not inv.tax.round_off:
        inv.assumptions.append(Assumption(
            field="invoice_total", value=str(base),
            reason="Grand total not detected; computed as taxable + GST."))

    inv.invoice_total = round(base + (inv.tax.round_off or 0), 2)
