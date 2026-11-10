"""Reconcile GSTR-2A against the purchase register (SOP 12).

Answers the question the CA actually needs: for the ITC we are claiming from
supplier invoices, has the supplier uploaded a matching invoice to the portal?

Matching is on (supplier GSTIN, normalised invoice number). Invoice numbers are
normalised because suppliers routinely print "SH01/26-27/1595" while uploading
"SH01-26-27-1595"; dropping separators and leading zeros avoids a wall of false
mismatches. Amounts are compared with a 1-rupee tolerance to absorb rounding.

Each line also carries ``diffs`` — the differences jotted down field by field
("Taxable +₹1,200.00", "Tax head: books CGST+SGST vs 2A IGST"). The prose
``remark`` says what to DO about a line; ``diffs`` says what actually differs,
which is what gets copied into the query raised with the supplier.
"""
from __future__ import annotations

import re
from typing import Dict, List

from pydantic import BaseModel

from .models import Invoice

_TOLERANCE = 1.0


def inr(n: float) -> str:
    """Indian-grouped rupees, "₹32,282.85" — lakh/crore commas, not thousands.

    str.format only knows western grouping, and these strings are read by a CA
    and pasted into a supplier query, so the grouping has to be the local one.
    """
    whole, _, frac = f"{abs(n):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            head, group = head[:-2], head[-2:]
            groups.insert(0, group)
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if n < 0 else ''}₹{whole}.{frac}"


def _signed(n: float) -> str:
    """"+₹1,200.00" / "-₹1,200.00" — books relative to 2A, sign always shown."""
    return f"{'+' if n >= 0 else ''}{inr(n)}"


class ReconLine(BaseModel):
    status: str                # matched | only_in_2a | only_in_books | value_mismatch
    party_name: str = ""
    party_gstin: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    books_taxable: float = 0.0
    books_tax: float = 0.0
    gstr2a_taxable: float = 0.0
    gstr2a_tax: float = 0.0
    taxable_diff: float = 0.0
    tax_diff: float = 0.0
    # Field-by-field differences against the reconciled GSTR-2A row, one short
    # phrase each; empty when the two sides agree on everything.
    diffs: List[str] = []
    remark: str = ""


class ReconSummary(BaseModel):
    books_count: int = 0
    gstr2a_count: int = 0
    matched: int = 0
    only_in_2a: int = 0
    only_in_books: int = 0
    value_mismatch: int = 0
    books_tax_total: float = 0.0
    gstr2a_tax_total: float = 0.0
    itc_at_risk: float = 0.0   # tax in books with no/short 2A backing
    lines: List[ReconLine] = []


def _key(inv: Invoice) -> tuple:
    num = re.sub(r"[^A-Z0-9]", "", (inv.invoice_number or "").upper())
    num = re.sub(r"(?<!\d)0+(\d)", r"\1", num)     # drop leading zeros in groups
    return ((inv.party_gstin or "").strip().upper(), num)


def _heads_of(inv: Invoice):
    """(cgst, sgst, igst, cess) from whichever breakup is authoritative here."""
    t = (inv.printed_tax if inv.source == "gstr2a" and inv.printed_tax is not None
         else inv.tax)
    return t.cgst, t.sgst, t.igst, t.cess


def _head_label(cgst: float, sgst: float, igst: float) -> str:
    heads = [n for n, v in (("CGST", cgst), ("SGST", sgst), ("IGST", igst))
             if abs(v) > _TOLERANCE]
    return "+".join(heads) or "none"


def _norm_name(name: str) -> str:
    """Party names for comparison only — the portal upper-cases and the invoice
    abbreviates, so "Acme Traders Pvt. Ltd." and "ACME TRADERS PVT LTD" are one
    supplier and must not raise a diff."""
    n = re.sub(r"[^A-Z0-9]+", " ", (name or "").upper())
    n = re.sub(r"\b(PVT|PRIVATE|LTD|LIMITED|LLP|CO|COMPANY|AND|THE)\b", " ", n)
    return " ".join(n.split())


def _diffs(b: Invoice, a: Invoice) -> List[str]:
    """What differs between the booked invoice and the GSTR-2A row it matched."""
    out: List[str] = []

    if b.invoice_date and a.invoice_date and b.invoice_date != a.invoice_date:
        out.append(f"Date: books {b.invoice_date} vs 2A {a.invoice_date}")

    d = round(b.taxable_total - a.taxable_total, 2)
    if abs(d) > _TOLERANCE:
        out.append(f"Taxable {_signed(d)}")

    bc, bs, bi, bcess = _heads_of(b)
    ac, as_, ai, acess = _heads_of(a)
    bl, al = _head_label(bc, bs, bi), _head_label(ac, as_, ai)
    if bl != al:
        # SOP 10 — intra vs inter-state posted differently on the two sides. The
        # per-head amounts below would then be noise, so this replaces them.
        out.append(f"Tax head: books {bl} vs 2A {al}")
    else:
        for head, dv in (("CGST", bc - ac), ("SGST", bs - as_), ("IGST", bi - ai)):
            if abs(dv) > _TOLERANCE:
                out.append(f"{head} {_signed(round(dv, 2))}")
    if abs(bcess - acess) > _TOLERANCE:
        out.append(f"Cess {_signed(round(bcess - acess, 2))}")

    if _norm_name(b.party_name) != _norm_name(a.party_name) and a.party_name:
        out.append(f"Party name: books “{b.party_name}” vs 2A “{a.party_name}”")

    if b.invoice_number != a.invoice_number:
        out.append(f"Invoice no. formatted differently: books “{b.invoice_number}” "
                   f"vs 2A “{a.invoice_number}”")

    return out


def _tax_of(inv: Invoice) -> float:
    """2A rows carry the supplier-uploaded figures in printed_tax; scanned
    invoices are posted on the computed figures."""
    if inv.source == "gstr2a" and inv.printed_tax is not None:
        p = inv.printed_tax
        return round(p.cgst + p.sgst + p.igst, 2)
    t = inv.tax
    return round(t.cgst + t.sgst + t.igst, 2)


def reconcile(invoices: List[Invoice]) -> ReconSummary:
    """Split a mixed batch into 2A rows and book purchases, then match."""
    books: Dict[tuple, Invoice] = {}
    two_a: Dict[tuple, Invoice] = {}

    for inv in invoices:
        if inv.direction != "purchase" or not inv.invoice_number:
            continue
        (two_a if inv.source == "gstr2a" else books)[_key(inv)] = inv

    s = ReconSummary(books_count=len(books), gstr2a_count=len(two_a), lines=[])

    for key in sorted(set(books) | set(two_a)):
        b, a = books.get(key), two_a.get(key)
        bt, at = (_tax_of(b) if b else 0.0), (_tax_of(a) if a else 0.0)
        bx, ax = (b.taxable_total if b else 0.0), (a.taxable_total if a else 0.0)
        s.books_tax_total += bt
        s.gstr2a_tax_total += at

        line = ReconLine(
            status="matched",
            party_name=(b or a).party_name,
            party_gstin=(b or a).party_gstin,
            invoice_number=(b or a).invoice_number,
            invoice_date=(b or a).invoice_date,
            books_taxable=round(bx, 2), books_tax=round(bt, 2),
            gstr2a_taxable=round(ax, 2), gstr2a_tax=round(at, 2),
            taxable_diff=round(bx - ax, 2), tax_diff=round(bt - at, 2),
        )

        if b and not a:
            line.status = "only_in_books"
            line.diffs = [f"Absent from GSTR-2A (books {inr(bt)})",
                          f"ITC {inr(bt)} unsupported"]
            line.remark = ("Purchase invoice not uploaded by the supplier in "
                           "GSTR-2A. ITC not reflected — follow up before claiming.")
            s.only_in_books += 1
            s.itc_at_risk += bt
        elif a and not b:
            line.status = "only_in_2a"
            line.diffs = [f"Absent from purchase register (2A {inr(at)})",
                          f"ITC {inr(at)} not claimed"]
            line.remark = ("Supplier uploaded this invoice but it is not in the "
                           "purchase register. Obtain the invoice and book it.")
            s.only_in_2a += 1
        elif abs(bt - at) > _TOLERANCE or abs(bx - ax) > _TOLERANCE:
            line.status = "value_mismatch"
            line.diffs = _diffs(b, a)
            line.remark = (f"Values differ — taxable {line.taxable_diff:+.2f}, "
                           f"tax {line.tax_diff:+.2f} (books vs 2A). Reconcile "
                           f"before claiming ITC.")
            s.value_mismatch += 1
            if bt > at:
                s.itc_at_risk += bt - at
        else:
            # Within tolerance on value, but the date / tax head / party name can
            # still differ. A tax-head divergence is the one that has to be
            # fixed — the totals agree, yet one side has called the supply
            # intra-state and the other inter-state, so the ITC lands in a head
            # GSTR-3B will not offset (SOP 10).
            line.diffs = _diffs(b, a)
            if any(d.startswith("Tax head:") for d in line.diffs):
                line.remark = ("Totals agree but the tax heads do not — one side "
                               "has treated the supply as intra-state and the "
                               "other as inter-state. Correct the classification "
                               "before claiming, or the ITC sits in the wrong head.")
            elif line.diffs:
                line.remark = ("Values match; the differences alongside are "
                               "presentational — verify before filing.")
            else:
                line.remark = "Matched with GSTR-2A."
            s.matched += 1

        s.lines.append(line)

    s.books_tax_total = round(s.books_tax_total, 2)
    s.gstr2a_tax_total = round(s.gstr2a_tax_total, 2)
    s.itc_at_risk = round(s.itc_at_risk, 2)
    return s
