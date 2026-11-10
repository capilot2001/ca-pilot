"""Parse reconstructed invoice text into the Invoice model.

Header fields (GSTINs, dates, parties, place of supply) are extracted with
label-anchored regexes. Line items are parsed row-by-row from the reconstructed
table. Anything uncertain is recorded as an Assumption rather than silently
guessed (per the user's "never assume without marking" rule).
"""
from __future__ import annotations

import re
from typing import List, Optional

# MIGRATION(A3/A5): this reading module imports the shared domain foundations
# (models/config/validate) and the tax-head matchers in-process from the server
# domain package. When the OCR service is split out, these move to a shared
# kernel so services/ocr no longer depends on `app` (tracked in TODO.local.md).
from app.domain.config import COMPANY, STATE_CODES, STATE_NAME_TO_CODE, fmt_rate
from app.domain.models import Invoice, LineItem, Assumption, TaxBreakup
from app.domain.validate import state_code_from_gstin
from app.domain.tax_heads import TAX_HEAD_RES

GSTIN_PATTERN = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")

# units commonly seen on Indian invoices -> canonical Tally symbol
UNIT_MAP = {
    "PCS": "PCS", "PC": "PCS", "NOS": "Nos", "NO": "Nos", "KGS": "Kgs",
    "KG": "Kg", "GM": "Gm", "GMS": "Gm", "PKT": "Pkt", "PKTS": "Pkt",
    "PAIR": "Pair", "PRS": "Pair", "CASE": "Case", "BOX": "Box",
    "MTR": "Mtr", "MTRS": "Mtr", "MTS": "Mtr", "M": "Mtr", "LTR": "Ltr",
    "LTRS": "Ltr", "LT": "Ltr", "BAG": "Bag", "BAGS": "Bag", "SET": "Set",
    "ROLL": "Roll", "BDL": "Bdl", "BTL": "Btl", "DOZ": "Doz", "UNIT": "Nos",
    "QTL": "Qtl", "TON": "Ton", "FT": "Ft", "SQF": "Sqft", "SQFT": "Sqft",
}
UNIT_TOKEN = re.compile(
    r"\b(" + "|".join(sorted(UNIT_MAP, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Same alternation, but tolerant of the dots invoices sprinkle through unit
# symbols ("k.g", "no.s"). Used only to recognise the unit that FOLLOWS a
# quantity, so the looser match can't swallow a word elsewhere in the row.
_UNIT_ALT = "|".join(
    r"\.?".join(re.escape(ch) for ch in u)
    for u in sorted(UNIT_MAP, key=len, reverse=True)
)

# A thousands separator can reach us as a period: OCR reads the comma in
# "47,118.400" as one often enough that the whole group has to stay inside
# a single match, or "47.118.400" splits into 47.118 and 400 and an
# HSN-summary rate comes out as 18000% instead of 18%.
NUM = r"[-+]?\d[\d,]*(?:\.\d{3})*(?:\.\d+)?"


def _num(s: str) -> Optional[float]:
    if s is None:
        return None
    s = str(s).replace(",", "").replace("INR", "").replace("₹", "").strip()
    s = s.strip("=ī ")
    # More than one period means the earlier ones are the thousands separators
    # the OCR misread; only the last can be the decimal point.
    if s.count(".") > 1:
        head, _, frac = s.rpartition(".")
        s = head.replace(".", "") + "." + frac
    try:
        return float(s)
    except ValueError:
        return None


def _all_numbers(s: str) -> List[float]:
    return [_num(m) for m in re.findall(NUM, s) if _num(m) is not None]


# OCR renders the rupee sign as whatever glyph it can find — €, *, ?, a stray
# quote — and it arrives glued to the figure. The decoration has to come off
# before a token is tested for being a number, or a whole Amount column reads
# as text and the line posts with no value at all.
_MONEY_EDGE = "₹€$*'\"`|:;()[]<>"


def _money(tok: str) -> Optional[float]:
    """The number this table cell holds, or None if it isn't one."""
    tok = tok.strip(_MONEY_EDGE)
    return _num(tok) if re.fullmatch(NUM, tok) else None


# ---------------------------------------------------------------------------
# date parsing
# ---------------------------------------------------------------------------
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DATE_RES = [
    re.compile(r"\b(\d{1,2})[\s/.-]+([A-Za-z]{3,9})[\s/.-]+(\d{2,4})\b"),
    re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b"),
]


def _parse_date(text: str):
    """Return (iso 'YYYY-MM-DD', display 'D-Mon-YYYY') or (None, None).

    Every match is tried, not just the first: an invoice number sitting beside
    the date reads as a near-miss ("G-26-27/0451" -> day 26, month 27), and
    abandoning the line on it left the real date one column over unread.
    """
    for rx in _DATE_RES:
        for m in rx.finditer(text):
            d, mo, y = m.groups()
            d = int(d)
            if mo.isalpha():
                mon = _MONTHS.get(mo[:3].lower())
                if not mon:
                    continue
            else:
                mon = int(mo)
            y = int(y)
            if y < 100:
                y += 2000
            if not (1 <= d <= 31 and 1 <= mon <= 12):
                continue
            mon_name = [k for k, v in _MONTHS.items() if v == mon][0].capitalize()
            return f"{y:04d}-{mon:02d}-{d:02d}", f"{d}-{mon_name}-{y}"
    return None, None


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
# label lines that are field captions, never values
_LABELS = re.compile(
    r"^(e-?Way\s*Bill|Delivery\s*Note|Dated?|Mode/?Terms|Reference\s*No|"
    r"Buyer'?s?\s*Order|Despatch|Dispatch|Dispatched|Destination|Bill\s*of\s*Lading|"
    r"Motor\s*Vehicle|Terms\s*of\s*Delivery|Other\s*Reference|Supplier'?s?\s*Ref|"
    r"e-?Invoice|IRN|Ack\s*No|Ack\s*Date|Consignee|Buyer|Invoice\s*No|"
    r"Tax\s*Invoice|ORIGINAL|DUPLICATE|TRIPLICATE|This\s*is\s*a|Created\s*by|"
    r"!!|GSTIN|State\s*Name|PAN|Pin\s*code|Pincode|Contact|Phone|Mobile|E-?Mail|"
    r"MSME|Place\s*of\s*supply|Company'?s?)\b", re.I)


# ---------------------------------------------------------------------------
# one file -> one or more invoices
# ---------------------------------------------------------------------------
def _page_gstins(text: str) -> set:
    return {m.group(0) for m in GSTIN_PATTERN.finditer(text)}


def invoice_number_in(text: str) -> str:
    """The invoice number printed on this text, or ""."""
    probe = Invoice()
    _parse_invoice_number(
        probe, [ln.strip() for ln in text.splitlines() if ln.strip()])
    return probe.invoice_number


def split_documents(pages: List[str]) -> List[List[int]]:
    """Group a file's page texts into one list of page indices per invoice.

    A CA scans a stack of bills into one PDF, so "one file, one invoice" turns
    the second bill into noise glued onto the first: its item rows land in the
    first invoice's table, its totals fight the first invoice's totals, and it
    never gets a voucher of its own. Splitting needs positive evidence though,
    because the opposite mistake -- cutting a genuine two-page invoice in half
    -- loses the half with the totals on it. So a page only starts a new
    document when it *contradicts* the one before:

      * it prints an invoice number, and a different one; or
      * it names GSTINs and shares none of them with the pages so far.

    A continuation page typically prints neither (just more item rows) or
    repeats the same number, and either way stays attached.
    """
    if len(pages) <= 1:
        return [list(range(len(pages)))]

    groups: List[List[int]] = [[0]]
    cur_no = invoice_number_in(pages[0])
    cur_gstins = _page_gstins(pages[0])
    for i in range(1, len(pages)):
        no = invoice_number_in(pages[i])
        gstins = _page_gstins(pages[i])
        starts_new = (
            (no and cur_no and no != cur_no)
            or (gstins and cur_gstins and not (gstins & cur_gstins)))
        if starts_new:
            groups.append([i])
            cur_no, cur_gstins = no, gstins
        else:
            groups[-1].append(i)
            cur_no = cur_no or no
            cur_gstins |= gstins
    return groups


def parse_invoice(rows_text: str, plain_text: str, source_file: str, engine: str) -> Invoice:
    inv = Invoice(source_file=source_file, ocr_engine=engine, raw_text=rows_text)
    rows = [ln.strip() for ln in rows_text.splitlines() if ln.strip()]
    plain = [ln.strip() for ln in (plain_text or rows_text).splitlines() if ln.strip()]

    # The number comes first: the address block and the date both have to be
    # able to tell the invoice-number column apart from their own.
    _parse_invoice_number(inv, plain)
    _parse_parties(inv, rows_text, plain)
    _parse_dates(inv, plain)
    _parse_place_of_supply(inv, plain_text or rows_text)
    _parse_items(inv, rows)
    _parse_totals(inv, rows)
    return inv


# ---- parties & direction ---------------------------------------------------
def _parse_parties(inv: Invoice, rows_text: str, plain: List[str]):
    gstins, seen = [], set()
    for m in GSTIN_PATTERN.finditer(rows_text):
        g = m.group(0)
        if g not in seen:
            seen.add(g)
            gstins.append(g)

    company = COMPANY.gstin.upper()
    if not gstins:
        inv.direction = "unknown"
        return

    seller = gstins[0]
    if seller == company:
        inv.direction = "sale"
        others = [g for g in gstins if g != company]
        counterparty = others[0] if others else ""
    else:
        inv.direction = "purchase"
        counterparty = seller

    inv.party_gstin = counterparty
    sc = state_code_from_gstin(counterparty)
    if sc:
        inv.party_state_code = sc
        inv.party_state = STATE_CODES.get(sc, "")

    inv.party_name = _guess_party_name(inv, plain)
    _parse_party_address(inv, plain)


# A cell holding nothing but a document-type word. "Tax Invoice" is already
# caught as a phrase, but OCR splits the two words into their own columns often
# enough that the halves have to be rejected on their own — otherwise the
# supplier ledger for a whole invoice comes out named "Invoice".
_DOC_WORD = re.compile(
    r"^(?:Tax|Invoice|Bill|Cash|Retail|Credit|Debit|Note|Estimate|Quotation|"
    r"Challan|Receipt|Voucher|Copy|Original|Duplicate|Triplicate)$", re.I)


def _guess_party_name(inv: Invoice, plain: List[str]) -> str:
    if inv.direction == "purchase":
        # supplier name = first substantial line at the top that isn't a caption,
        # an IRN/Ack hash, a blessing, or a copy-marker.
        picked = ""
        for ln in plain[:14]:
            # One column at a time. A scan of a letterhead picks up slivers of
            # the faded logo behind it as their own columns ("RDWARE" beside
            # "SUNIL HARDWARE AND MILL STORES"), and gluing the row together
            # would prefix that debris onto the ledger name. The name is the
            # substantial column in its row; the debris is a fragment.
            cands = []
            for probe in re.split(r"\s{2,}", ln.strip()):
                probe = probe.lstrip("(:!. ")
                if len(probe) < 4:
                    continue
                if _LABELS.match(probe) or _DOC_WORD.match(probe):
                    continue
                if re.search(r"GSTIN|RECIPIENT|TRANSPORTER|NAMAH|GANESH|"
                             r"^Tax\s*Invoice$|DUPLICATE|TRIPLICATE|e-?Invoice",
                             probe, re.I):
                    continue
                if re.fullmatch(r"[0-9a-fA-F:\- ]{12,}", probe):  # IRN / Ack hash
                    continue
                if _parse_date(probe)[0]:                          # a date line
                    continue
                if not re.search(r"[A-Za-z]{3,}", probe):
                    continue
                cands.append(probe)
            if not cands:
                continue
            name = _strip_suffix(max(cands, key=len))
            if not picked:
                picked = name
            elif name.upper().startswith(picked.upper()) and len(name) > len(picked):
                # The logo prints the brand ("DULEVO") and the letterhead line
                # under it prints the legal name ("DULEVO INDIA PRIVATE
                # LIMITED"). The ledger wants the legal one, and one being a
                # prefix of the other is what identifies the pair — anything
                # else on the page is left alone.
                return name
        if picked:
            return picked
    else:  # sale -> buyer name follows the "Buyer"/"Consignee" caption
        for kw in (r"Buyer\s*\(Bill", r"\bBuyer\b", r"Consignee"):
            for i, ln in enumerate(plain):
                if re.search(kw, ln, re.I):
                    for j in range(i + 1, min(len(plain), i + 5)):
                        cand = plain[j]
                        if len(cand) > 3 and not _LABELS.match(cand) and \
                           not re.search(r"GSTIN|State|Pincode|Address|Ship", cand, re.I):
                            return _strip_suffix(cand)
    return ""


# caption words that, when they appear mid-line (OCR column-merge), mark the end
# of the party name
_INLINE_LABEL = re.compile(
    r"\s{2,}(?:Invoice\s*No|Dated|e-?Way|GSTIN|State\s*Name|Delivery\s*Note|"
    r"Buyer|Consignee|Reference|Despatch|Dispatch|Contact|PAN|Pin\s*code|"
    r"Mode/?Terms|Place\s*of\s*supply|Ack\b|IRN)\b.*$", re.I)


def _strip_suffix(s: str) -> str:
    s = _INLINE_LABEL.sub("", s)                  # cut merged caption columns
    s = re.sub(r"\s+(?:Invoice\s*No\.?|Dated)\b.*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-–]\s*\(.*?\).*$", "", s)    # drop "- (FY-2026 To 2027)"
    s = re.sub(r"\s{2,}", " ", s)
    return _clean_name(s)


def _clean_name(s: str) -> str:
    s = re.sub(r"\s{2,}", " ", s).strip(" .:,-")
    return s


# captions that end the party's address block
_ADDR_STOP = re.compile(
    r"^(GSTIN|State\s*Name|State\b|PAN|Pin\s*code|Pincode|Contact|Phone|Mobile|"
    r"E-?Mail|Place\s*of\s*supply|Buyer|Consignee|Supplier|Invoice\s*No|Dated?|"
    r"Delivery|Despatch|Dispatch|Terms|Mode/?Terms|Reference|Other\s*Reference|"
    r"Destination|Description|MSME|Sl$|Sr$|No\.$)\b", re.I)


def _parse_party_address(inv: Invoice, plain: List[str]):
    for ln in plain:
        m = re.search(r"Pin\s*code\s*[:.]?\s*(\d{6})", ln, re.I)
        if m:
            inv.party_pincode = m.group(1)
            break

    # The address is whatever is printed between the party's name and the first
    # field caption below it. Reference doc §3.6 counts it among the twelve
    # buyer/supplier attributes: an invoice missing it still imports, but lands
    # in GSTR-1/3B as "Uncertain".
    if not inv.party_name or inv.party_address:
        return
    for i, ln in enumerate(plain):
        if _strip_suffix(ln) != inv.party_name:
            continue
        parts = []
        for cand in plain[i + 1:i + 9]:
            # Only the party's own column. The block beside it is a different
            # field, and a row where that column alone printed something is the
            # neighbour's row, not a continuation of the address.
            cand = re.split(r"\s{2,}", cand.strip())[0].strip()
            if not cand or _ADDR_STOP.match(cand) or GSTIN_PATTERN.search(cand):
                break
            if inv.invoice_number and inv.invoice_number in cand:
                continue
            if len(cand) < 5:
                continue      # a sliver of the letterhead logo, not a line
            parts.append(cand)
        if parts:
            inv.party_address = ", ".join(parts)
            break

    # The PIN is usually printed inside the last address line ("UTTAR
    # PRADESH-201305") rather than behind a caption of its own, and without it
    # every voucher carries the "Uncertain in GSTR-1/3B" warning.
    if not inv.party_pincode and inv.party_address:
        m = re.search(r"(?<!\d)([1-9]\d{5})(?!\d)", inv.party_address)
        if m:
            inv.party_pincode = m.group(1)


# ---- invoice number --------------------------------------------------------
def _looks_like_inv_no(tok: str) -> bool:
    if GSTIN_PATTERN.match(tok):
        return False
    if re.fullmatch(r"\d{11,}", tok):          # e-way bill / ack no.
        return False
    if _parse_date(tok)[0]:                     # a date
        return False
    if _LABELS.match(tok) or tok.lower() in {"no", "no.", "bill", "way", "note"}:
        return False
    return bool(re.search(r"[A-Za-z0-9]", tok)) and 1 <= len(tok) <= 32


def _parse_invoice_number(inv: Invoice, plain: List[str]):
    for i, ln in enumerate(plain):
        if re.match(r"Invoice\s*No\.?\s*$", ln, re.I):
            # vertical: value is the next non-label line
            for j in range(i + 1, min(len(plain), i + 6)):
                tok = plain[j].strip()
                if _LABELS.match(tok):
                    continue
                first = tok.split()[0] if tok.split() else ""
                if _looks_like_inv_no(first):
                    inv.invoice_number = first
                    return
        # inline, one column at a time. A run of 2+ spaces is a column break
        # everywhere else in this parser, and it is one here too: in
        # "Invoice No.  e-Way Bill No.  Dated" the label owns its column and
        # what follows is the *next header*, not the value.
        cells = re.split(r"\s{2,}", ln.strip())
        for k, cell in enumerate(cells):
            m = re.match(r"Invoice\s*No\.?\s*[:#]?\s*(.*)$", cell, re.I)
            if not m:
                continue
            rest = m.group(1).strip()
            if not rest and k + 1 < len(cells):
                rest = cells[k + 1].strip()
                if _LABELS.match(rest):
                    rest = ""
            first = rest.split()[0] if rest.split() else ""
            if _looks_like_inv_no(first):
                inv.invoice_number = first
                return


# ---- dates -----------------------------------------------------------------
def _parse_dates(inv: Invoice, plain: List[str]):
    # The invoice's own date, before any other date printed on it. A header
    # block sets several side by side — "Purchase Order No. / Dated" sits one
    # column over from "Invoice No. / Date" on the DULEVO template — and a
    # plain "Dated" scan reads whichever the OCR happened to emit first, which
    # posted the purchase-order date as the voucher date.
    if inv.invoice_number:
        for ln in plain:
            if inv.invoice_number in ln:
                iso, disp = _parse_date(ln)
                if iso:
                    inv.invoice_date, inv.invoice_date_display = iso, disp
                    return

    # otherwise a date on or right after a "Dated"/"Date" caption
    for i, ln in enumerate(plain):
        if re.search(r"\bDated\b|\bInvoice\s*Date\b", ln, re.I):
            iso, disp = _parse_date(ln)
            if not iso:
                for j in range(i + 1, min(len(plain), i + 4)):
                    iso, disp = _parse_date(plain[j])
                    if iso:
                        break
            if iso:
                inv.invoice_date, inv.invoice_date_display = iso, disp
                return
    iso, disp = _parse_date("\n".join(plain))
    if iso:
        inv.invoice_date, inv.invoice_date_display = iso, disp


# ---- place of supply -------------------------------------------------------
def _parse_place_of_supply(inv: Invoice, text: str):
    m = re.search(r"Place\s*of\s*supply\s*[:.]?\s*([A-Za-z &]+?)(?:\s{2,}|$|Contact|Code)", text, re.I)
    if m:
        name = m.group(1).strip()
        code = STATE_NAME_TO_CODE.get(name.lower())
        if code:
            inv.place_of_supply = STATE_CODES[code]
            inv.place_of_supply_code = code
            return
    # Nothing printed: classify._infer_place_of_supply fills it from the
    # parties. It is derived, not read, and it has to be derived after every
    # later correction to them — not once, here, off whatever the parse had.


# ---- line items ------------------------------------------------------------
# The item table's own header row: it names the HSN column and at least one
# money/quantity column beside it.
_ITEM_HEAD = re.compile(
    r"(?=.*\bHSN\b|.*\bSAC\b)"
    r"(?=.*\b(?:Quantity|Qty|Rate|Price|Amount|Value)\b)", re.I)
# ...and the first caption underneath it that is no longer a goods row.
_ITEM_END = re.compile(
    r"^(?:Total|Sub\s*Total|Grand\s*Total|Amount\s*Chargeable|Tax\s*Summary|"
    r"Taxable\s*(?:amount|value)|HSN/?\s*SAC|Declaration|Terms|Bank\s*Details|"
    r"Payment\s*Mode|Company'?s?\s*Bank)\b", re.I)


def _item_band(lines: List[str]) -> range:
    """Indices of the rows between the item table's header and its totals.

    Only inside this band is a row without a serial number read as an item.
    Outside it the serial is the only thing keeping the HSN summary's own rows
    ("84241000  2,542.38  9  228.81 …") from being posted a second time as
    goods, so the relaxation has to be bounded by the table it applies to.
    """
    for i, ln in enumerate(lines):
        if not _ITEM_HEAD.match(ln):
            continue
        for j in range(i + 1, len(lines)):
            if _ITEM_END.match(lines[j]):
                return range(i + 1, j)
        return range(i + 1, len(lines))
    return range(0)


def _parse_items(inv: Invoice, lines: List[str]):
    band = _item_band(lines)
    # Which 4-digit codes this invoice itself calls an HSN. Four digits is a
    # legal HSN width, but it is also the shape of a year, an invoice number
    # and a part number, so a bare \d{4} anywhere on the page would post
    # "2026" and "1595" as goods. The invoice's own tax summary is the
    # authority on which codes are real, and a supplier printing 4-digit HSNs
    # is required to print that summary.
    declared = set(hsn_rate_map("\n".join(lines)))
    for i, ln in enumerate(lines):
        item = _parse_item_line(ln, require_serial=i not in band,
                               declared_hsn=declared)
        if item:
            _reconcile_item_math(inv, item)
            inv.items.append(item)


def _reconcile_item_math(inv: Invoice, it: LineItem):
    """Quantity x rate has to equal the printed line amount.

    When it doesn't, the RATE is the column that was misread: templates print
    two of them (a list rate beside the net rate actually charged, "69.500
    58.898 KGS"), and only one can be picked from position. Quantity sits next
    to its unit and is printed once, and the amount is what the accounting is
    built from — so those two arbitrate and the rate is re-derived.
    """
    if not it.quantity or it.rate is None or not it.taxable_value:
        return
    # A discounted row reconciles against the NET of the discount — skipping the
    # check for those rows entirely let a misread rate through unnoticed.
    factor = 1 - (it.disc_pct or 0) / 100
    net = it.quantity * it.rate * factor
    tolerance = max(0.05, abs(it.taxable_value) * 0.005)
    if abs(net - it.taxable_value) <= tolerance:
        return

    # Some templates (Vyapar's default among them) print an Amount column that
    # is INCLUSIVE of GST: "2 Nos  1,271.19  457.63 (18%)  3,000.01". Posting
    # 3,000.01 as the taxable value would tax the tax. The row's own three
    # figures only agree on one reading, so the row settles it itself — no
    # invoice-level guess is involved.
    if it.gst_rate and abs(net * (1 + it.gst_rate / 100) - it.taxable_value) <= tolerance:
        gross = it.taxable_value
        it.taxable_value = it.amount = round(net, 2)
        inv.assumptions.append(Assumption(
            field=f"taxable_value[{it.description[:24]}]", value=f"{it.taxable_value:g}",
            reason=f"The Amount column prints {gross:g}, which is quantity x rate "
                   f"plus {fmt_rate(it.gst_rate)}% GST — this template bills gross. "
                   f"The taxable value posted is the net figure; GST is added "
                   f"once, by the tax ledgers."))
        return

    fixed = round(it.taxable_value / it.quantity, 4)
    disc_note = (f" less the printed {it.disc_pct:g}% discount" if it.disc_pct else "")
    inv.assumptions.append(Assumption(
        field=f"rate[{it.description[:24]}]", value=f"{fixed:g}",
        reason=f"Printed rate {it.rate:g} x quantity {it.quantity:g}{disc_note} does "
               f"not make the line amount {it.taxable_value:g} — the row carries more "
               f"than one rate column. Rate re-derived as amount / quantity; the "
               f"taxable value posted is unchanged."))
    it.rate = fixed
    # The derived rate is already net, so leaving the discount on the line would
    # have it applied a second time downstream.
    it.disc_pct = None


def _short_hsn(body: str, declared: Optional[set]):
    """A 4-digit HSN, but only one the invoice's tax summary also declares."""
    if not declared:
        return None
    for m in re.finditer(r"(?<!\.)\b(\d{4})\b(?!\.)", body):
        if m.group(1) in declared:
            return m
    return None


def _norm_unit(tok: str) -> Optional[str]:
    key = re.sub(r"[.\s]", "", tok).upper()
    return UNIT_MAP.get(key)


# TallyPrime prints a compound-unit quantity as "<whole>-<sub> <unit>":
# "134-400 k.g" is 134.400 kg, "168- 0 k.g" is 168 kg, "1-0 case" is 1 case.
# Left as-is it tokenises into garbage (the hyphen splits it and the whole part
# is dropped), so it is collapsed to a plain decimal before the row is read.
# The unit lookahead is what keeps part numbers like "1441-7" out of this.
_COMPOUND_QTY = re.compile(
    rf"(?<![\w.])(\d[\d,]*)\s*-\s*(\d+)\s+(?=(?:{_UNIT_ALT})\b)", re.I)


def _decompound_qty(text: str) -> str:
    def repl(m: "re.Match") -> str:
        whole, sub = m.group(1).replace(",", ""), m.group(2)
        if int(sub) == 0:
            return whole + " "
        # The sub-unit is thousandths of the main unit (k.g of 1000 gm is the
        # compound this template uses). _reconcile_item_math cross-checks the
        # result against the printed amount.
        return f"{whole}.{sub.zfill(3)} "
    return _COMPOUND_QTY.sub(repl, text)


def _pick_qty_rate(cand: List[float], amount: Optional[float],
                   disc: Optional[float]) -> tuple:
    """Choose (quantity, rate) out of the numbers printed before the amount.

    Taking the first two positionally is wrong whenever the row carries an
    extra numeric column. This template prints a Part No. that is sometimes all
    digits ("1604010626  20.000 PCS  551.00"), and it is indistinguishable from
    a quantity by shape alone — read positionally it becomes a quantity of 1.6
    billion.

    The line's own arithmetic is the arbiter instead: quantity x rate, less any
    discount, has to make the printed amount. The first ordered pair that does
    is the real pair, whatever else the row printed. Falls back to the
    positional reading when nothing reconciles, leaving _reconcile_item_math to
    re-derive the rate.
    """
    if amount:
        tol = max(0.05, abs(amount) * 0.005)
        factor = 1 - (disc or 0) / 100
        for i in range(len(cand)):
            for j in range(i + 1, len(cand)):
                if abs(cand[i] * cand[j] * factor - amount) <= tol:
                    return cand[i], cand[j]
    return cand[0], cand[1]


def _parse_item_line(ln: str, require_serial: bool = True,
                     declared_hsn: Optional[set] = None) -> Optional[LineItem]:
    # A serial number opens the row on most templates, and outside the item
    # table it is the only thing separating a goods line from prose. Inside the
    # table `require_serial` is dropped: a charge row ("Add FREIGHT CHARGES")
    # often carries no serial, and losing it loses its value off the invoice.
    m = re.match(r"^(\d{1,3})\s+(.*)$", ln)
    if m:
        body = m.group(2)
    elif require_serial:
        return None
    else:
        body = ln

    # HSN/SAC: the first standalone code, no decimal point. The GST law allows
    # 4, 6 and 8 digits (turnover decides which a supplier must print) and SAC
    # is 6, so a 4-digit code like 2523 for cement is perfectly valid — reading
    # only 8 and 6 dropped the whole line, and with it the invoice's value.
    # Widest first: 84798999 must not be read as the 4-digit 8479.
    hsn_m = (re.search(r"(?<!\.)\b(\d{8})\b(?!\.)", body)
             or re.search(r"(?<!\.)\b(\d{6})\b(?!\.)", body)
             or _short_hsn(body, declared_hsn))
    if not hsn_m:
        return None  # no HSN -> not a goods line
    hsn = hsn_m.group(1)

    desc = body[:hsn_m.start()].strip(" .-")
    rest = body[hsn_m.end():]
    # collapse a duplicated HSN that some templates print twice
    rest = re.sub(r"^\s*" + re.escape(hsn) + r"\b", "", rest).strip()
    rest = _decompound_qty(rest)

    # GST rate: first "<n> %" after HSN ; discount % is a later "<n> %"
    pcts = re.findall(rf"({NUM})\s*%", rest)
    gst_rate = _num(pcts[0]) if pcts else None
    disc = _num(pcts[-1]) if len(pcts) > 1 else None

    # Every percentage is CUT OUT of the row rather than the row being sliced
    # at the first one. Column order varies — "HSN Qty Rate Gst% Amount" and
    # "HSN Qty Unit Rate Gst%(tax) Amount" are both common — so reading only
    # what follows the percentage threw away the quantity and rate on any
    # template that prints GST% before the Amount column, which is most of
    # them. What is left is the row's money/quantity columns, in order.
    figures = re.sub(rf"{NUM}\s*%", " ", rest)

    # Keep only *numeric* cells (drops part numbers like TCTS430 / 1441-7) and
    # capture the first recognised unit token.
    unit = None
    nums: List[float] = []
    for tok in figures.split():
        v = _money(tok)
        if v is not None:
            nums.append(v)
        elif unit is None:
            u = _norm_unit(tok)
            if u:
                unit = u

    qty = rate = amount = None
    if nums:
        amount = nums[-1]
    if len(nums) >= 3:
        qty, rate = _pick_qty_rate(nums[:-1], amount, disc)
    elif len(nums) == 2:
        # "<qty> <amount>" (no rate column) or "<rate> <amount>" (no quantity
        # column, as on a lump-sum charge row). The unit beside the figures is
        # what tells them apart; without one, "Add FREIGHT CHARGES  120000.0
        # 120000.00" would post a quantity of 120,000.
        if unit:
            qty, amount = nums[0], nums[1]
            rate = round(amount / qty, 4) if qty else None
        else:
            rate, amount = nums[0], nums[1]
            qty = round(amount / rate, 4) if rate else None

    return LineItem(
        description=_clean_name(desc), hsn_sac=hsn, quantity=qty, unit=unit or "",
        rate=rate, disc_pct=disc, taxable_value=amount, gst_rate=gst_rate,
        amount=amount,
    )


# ---- HSN/SAC tax summary ---------------------------------------------------
# The block printed under the item table:
#
#   HSN/SAC   Taxable   CGST          SGST/UTGST     Total
#             Value     Rate Amount   Rate Amount    Tax Amount
#   83111000  2,280.00  9%   205.20   9%   205.20    410.40
#
# It is the only place TallyPrime's own invoice print states a per-item GST
# rate — the item rows carry no rate column at all — so on that template this
# block IS the rate source, and it is the only source that survives a
# mixed-rate invoice (18% pipe, 5% rope, 0% shovel on one bill).
_HSN_SUMMARY_HEAD = re.compile(r"^HSN/?\s*SAC\b.*\b(?:Taxable|Tax\s*Amount)\b", re.I)
_MAX_GST_RATE = 28.0        # the highest slab; anything above is a misread
_HSN_SUMMARY_ROW = re.compile(r"^(\d{4,8})\s+(.*\S)\s*$")


def hsn_rate_map(rows_text: str) -> dict:
    """{HSN/SAC -> combined GST rate %} read from the tax summary, or {}.

    CGST and SGST are each printed at half the rate, so a row's percentages are
    summed; an inter-state row prints IGST alone and sums to itself. Where the
    row also prints amounts, total tax / taxable value overrides the summed
    percentages — that survives a percentage column being misread.
    """
    out: dict = {}
    in_block = False
    for ln in (rows_text or "").splitlines():
        ln = ln.strip()
        if _HSN_SUMMARY_HEAD.match(ln):
            in_block = True
            continue
        if not in_block:
            continue
        if re.match(r"^Total\b", ln, re.I):
            in_block = False          # a second page repeats the whole block
            continue
        m = _HSN_SUMMARY_ROW.match(ln)
        if not m:
            continue                  # stray line inside the block (footers etc.)
        hsn, rest = m.group(1), m.group(2)
        pcts = [_num(p) for p in re.findall(rf"({NUM})\s*%", rest)]
        if not pcts or any(p is None for p in pcts):
            continue
        rate = round(sum(pcts), 2)
        nums = _all_numbers(re.sub(rf"{NUM}\s*%", " ", rest))
        if len(nums) >= 2 and nums[0]:
            # total tax / taxable value, where the last column really is the
            # tax. Some templates end the row with the tax-INCLUSIVE total
            # instead, and that reads as 118% on an 18% supply — so the derived
            # figure only wins if it is a rate at all. No GST slab exceeds 28%.
            derived = round(nums[-1] / nums[0] * 100, 2)
            if abs(derived - rate) > 0.05 and 0 <= derived <= _MAX_GST_RATE:
                rate = derived
        out[hsn] = rate
    return out


# ---- totals ----------------------------------------------------------------
# A caption that names the payable figure outright. Anchored to the start of a
# cell (a run of 2+ spaces is a column break, as everywhere else here) so a
# mention inside prose can't be mistaken for the total's own row.
_GRAND_TOTAL = re.compile(
    r"(?:^|\s{2,})(?:Grand\s*Total|Total\s*Invoice\s*Value|Invoice\s*Value|"
    r"Total\s*Amount(?:\s*(?:Payable|Due))?|Net\s*(?:Amount\s*)?Payable|"
    r"Amount\s*Payable|Bill\s*Amount)\b", re.I)
_SUB_TOTAL = re.compile(r"(?:^|\s{2,})Sub\s*Total\b", re.I)
_ROUND_OFF = re.compile(r"\bR\.?\s*Off\b|\bRound\s*Off\b", re.I)


def _labelled_amount(ln: str, label: "re.Pattern") -> Optional[float]:
    """The money figure a caption owns: the largest number printed after it."""
    m = label.search(ln)
    if not m:
        return None
    nums = _all_numbers(ln[m.end():])
    return max(nums) if nums else None


def _parse_totals(inv: Invoice, lines: List[str]):
    inv.taxable_total = round(sum(i.taxable_value or 0 for i in inv.items), 2)

    # the item table's "Total" row is printed before the "Amount Chargeable
    # (in words)" block; the HSN tax-summary table (which also has a "Total"
    # row) comes after it.
    head = lines
    for idx, ln in enumerate(lines):
        if re.search(r"Amount\s*Chargeable", ln, re.I):
            head = lines[:idx]
            break

    # explicit round off
    round_off = None
    for ln in lines:
        if _ROUND_OFF.search(ln):
            # "Less : R.Off  (-)0.40" is a deduction: neither the bracketed minus
            # nor the "Less" caption survives _all_numbers, so the sign has to be
            # taken from the text before the digits are pulled out.
            negative = bool(re.search(r"\(-\)|\bLess\b", ln, re.I))
            nums = _all_numbers(_ROUND_OFF.sub("", ln))
            if nums:
                round_off = -abs(nums[0]) if negative else nums[0]
                inv.tax.round_off = round_off
            break

    # The payable figure, in order of how directly the invoice states it. A
    # labelled "Grand Total" is read wherever it is printed — on the templates
    # that have one it sits BELOW the amount-in-words block, past the cut above.
    grand = sub_total = None
    for ln in lines:
        grand = _labelled_amount(ln, _GRAND_TOTAL) or grand
        sub_total = _labelled_amount(ln, _SUB_TOTAL) or sub_total

    if grand is None:
        # Otherwise the item table's own "Total" row. The largest candidate
        # wins, not the last: a template with no amount-in-words caption leaves
        # the HSN summary's "TOTAL  2,542.38 …" (a per-HSN taxable, always
        # smaller) in the running behind the real one.
        for ln in head:
            if re.match(r"^Total\b", ln, re.I) and not re.search(r"Tax\s*Amount", ln, re.I):
                nums = _all_numbers(ln)   # qty may also appear; total is largest
                if nums:
                    grand = max(nums + ([grand] if grand else []))
        # A sub-total plus the round-off printed under it IS the payable, and
        # the two figures agreeing is what says the one just read was the
        # sub-total rather than the total itself.
        if grand and round_off and sub_total and abs(grand - sub_total) < 0.005:
            grand = round(grand + round_off, 2)

    if grand:
        inv.invoice_total = grand   # provisional; classify() reconciles vs computed

    _parse_printed_tax(inv, head)


# ---- printed tax heads -----------------------------------------------------
# A labelled tax line, e.g. "CGST 9%   675.00" / "Add: IGST @ 18%  1,234.00".
# The rate (a bare "9%" / "@18%") is stripped before taking the amount so the
# percentage is never mistaken for the tax value.
# TAX_HEAD_RES (the CGST/SGST/IGST matchers) is a domain vocabulary shared with
# classify; it now lives in app.domain.tax_heads and is imported at the top of
# this module. Behaviour is unchanged.


def _parse_printed_tax(inv: Invoice, lines: List[str]):
    """Capture CGST/SGST/IGST exactly as printed (SOP 10 wrong-tax-head check).

    These values are diagnostic only — classify() keeps its own per-line computed
    figures for posting, so OCR noise here can never unbalance a voucher.
    """
    found: dict = {}
    for ln in lines:
        # a line naming more than one head is a summary/table header, not a value
        heads = [k for k, rx in TAX_HEAD_RES.items() if rx.search(ln)]
        if len(heads) != 1:
            continue
        head = heads[0]
        stripped = re.sub(r"[-+]?\d[\d,]*(?:\.\d+)?\s*%", " ", ln)   # drop "18 %"
        stripped = TAX_HEAD_RES[head].sub(" ", stripped)
        nums = _all_numbers(stripped)
        if nums:
            # A mixed-rate invoice prints one line per rate ("Cgst 9% … 1,958.40"
            # then "2.5% Cgst … 262.08"); the head's printed total is their sum,
            # and taking only the first understates it by the other slabs.
            found[head] = round(found.get(head, 0.0) + abs(nums[-1]), 2)

    if found:
        inv.printed_tax = TaxBreakup(
            cgst=found.get("cgst", 0.0),
            sgst=found.get("sgst", 0.0),
            igst=found.get("igst", 0.0),
        )
