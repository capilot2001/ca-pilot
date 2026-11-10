"""The GSTR-2A reconciliation as a sendable report — .xlsx and .pdf.

The point of this file is that the reconciliation stops being something the CA
reads on screen and becomes the attachment that goes to the client or to the
supplier being chased. So both outputs carry the same three blocks: who it is
for, the totals that decide whether ITC is safe, and one row per invoice with
the differences jotted down (``ReconLine.diffs``) next to the action to take.

Rows are ordered by how much they need attention — books-only first (that is
the ITC actually at risk), matched last — because the reader works down the
page and stops when the rows stop mattering.
"""
from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path
from typing import List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .config import COMPANY
from .reconcile import ReconSummary, ReconLine, inr

# Worst first: an ITC claim with no 2A backing is the reason this report exists.
_ORDER = {"only_in_books": 0, "value_mismatch": 1, "only_in_2a": 2, "matched": 3}

STATUS_LABEL = {
    "matched": "Matched",
    "only_in_2a": "Only in GSTR-2A",
    "only_in_books": "Only in books",
    "value_mismatch": "Value mismatch",
}

# Shared column plan: (heading, width in Excel chars, width in PDF points).
_COLUMNS = [
    ("Status",       16,  60),
    ("Party",        30, 104),
    ("GSTIN",        18,  86),
    ("Invoice",      18,  74),
    ("Date",         12,  52),
    ("Books tax",    14,  62),
    ("2A tax",       14,  62),
    ("Diff",         14,  62),
    ("Differences",  46, 142),
    ("Action",       52, 140),
]


def _sorted_lines(s: ReconSummary) -> List[ReconLine]:
    return sorted(s.lines, key=lambda l: (_ORDER.get(l.status, 9), l.party_name.lower()))


def _row(l: ReconLine) -> list:
    return [
        STATUS_LABEL.get(l.status, l.status), l.party_name or "—", l.party_gstin or "—",
        l.invoice_number or "—", l.invoice_date or "—",
        l.books_tax, l.gstr2a_tax, l.tax_diff,
        "\n".join(f"• {d}" for d in l.diffs) or "No differences",
        l.remark,
    ]


def report_filename(ext: str) -> str:
    """"GST_Reconciliation_Narsingh_Prasad_2026-08-31.xlsx" — safe for a
    Content-Disposition header (no quotes, no separators, ASCII only)."""
    stem = re.sub(r"[^A-Za-z0-9]+", "_", COMPANY.name).strip("_")[:40] or "Client"
    return f"GST_Reconciliation_{stem}_{date.today().isoformat()}.{ext}"


def _meta(s: ReconSummary) -> List[tuple]:
    """The header key/value block both formats print, in one place."""
    return [
        ("Client", COMPANY.name),
        ("GSTIN", f"{COMPANY.gstin}  ({COMPANY.state})"),
        ("Report", "GSTR-2A ↔ purchase register (ITC reconciliation)"),
        ("Generated", date.today().strftime("%d-%b-%Y")),
        ("Coverage", f"{s.books_count} invoice(s) in books · {s.gstr2a_count} row(s) in GSTR-2A"),
        ("Outcome", f"{s.matched} matched · {s.value_mismatch} value mismatch · "
                    f"{s.only_in_books} not in 2A · {s.only_in_2a} not booked"),
        ("ITC per books", inr(s.books_tax_total)),
        ("ITC per GSTR-2A", inr(s.gstr2a_tax_total)),
        ("ITC at risk", inr(s.itc_at_risk)),
    ]


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
_INK = "1F2937"
_HEAD_FONT = Font(bold=True, color="FFFFFF", size=10)
_HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
_MONEY = '#,##,##0.00;[Red]-#,##,##0.00'      # Indian lakh grouping
_THIN = Side(style="thin", color="D9D9D9")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_STATUS_FILL = {
    "only_in_books": PatternFill("solid", fgColor="FDE7E9"),
    "value_mismatch": PatternFill("solid", fgColor="FFF4DA"),
    "only_in_2a": PatternFill("solid", fgColor="FFF9E6"),
    "matched": PatternFill("solid", fgColor="EAF7F0"),
}
_STATUS_INK = {"only_in_books": "B42318", "value_mismatch": "B54708",
               "only_in_2a": "B54708", "matched": "067647"}


def build_recon_workbook(s: ReconSummary) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "GST Reconciliation"

    ws["A1"] = "GST Reconciliation Report"
    ws["A1"].font = Font(bold=True, size=15, color=_INK)
    r = 3
    for label, value in _meta(s):
        ws.cell(row=r, column=1, value=label).font = Font(bold=True, size=10, color="6B7280")
        c = ws.cell(row=r, column=2, value=value)
        c.font = Font(size=10, bold=label == "ITC at risk",
                      color="B42318" if label == "ITC at risk" and s.itc_at_risk else _INK)
        r += 1

    head_row = r + 1
    for i, (heading, _, _) in enumerate(_COLUMNS, start=1):
        cell = ws.cell(row=head_row, column=i, value=heading)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL
        cell.alignment = Alignment(horizontal="right" if i in (6, 7, 8) else "left",
                                   vertical="center")
    ws.freeze_panes = ws.cell(row=head_row + 1, column=1)

    for n, line in enumerate(_sorted_lines(s), start=head_row + 1):
        for i, value in enumerate(_row(line), start=1):
            cell = ws.cell(row=n, column=i, value=value)
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=i in (2, 9, 10),
                                       horizontal="right" if i in (6, 7, 8) else "left")
            if i in (6, 7, 8):
                cell.number_format = _MONEY
            if i == 1:
                cell.font = Font(bold=True, size=10, color=_STATUS_INK.get(line.status, _INK))
        fill = _STATUS_FILL.get(line.status)
        if fill:
            ws.cell(row=n, column=1).fill = fill

    ws.auto_filter.ref = (f"A{head_row}:{get_column_letter(len(_COLUMNS))}"
                          f"{head_row + len(s.lines)}")
    for i, (_, width, _) in enumerate(_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
# Helvetica is a Type-1 font and the rupee sign (U+20B9, notified in 2010) is
# missing from it — and from plenty of TTFs that look Unicode-complete, Arial
# Unicode MS included, which is old enough to predate the glyph. It prints as a
# hollow box with no error, so a candidate is only accepted after its cmap is
# checked for that one codepoint; otherwise the report falls back to "Rs.".
_TTF_CANDIDATES = [
    # Debian/Ubuntu — fonts-dejavu-core, installed by the Dockerfile.
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    # macOS — SF Pro (the system font) carries ₹; Arial Unicode does not.
    ("/System/Library/Fonts/SFNS.ttf", None),
    ("/System/Library/Fonts/Supplemental/Georgia.ttf",
     "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"),
]
_RUPEE = 0x20B9
_FONTS: Optional[tuple] = None


def _fonts() -> tuple:
    """(regular, bold, unicode_ok) — resolved once per process."""
    global _FONTS
    if _FONTS is not None:
        return _FONTS
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    _FONTS = ("Helvetica", "Helvetica-Bold", False)
    for regular, bold in _TTF_CANDIDATES:
        if not Path(regular).is_file():
            continue
        try:
            face = TTFont("LFSans", regular)
            if _RUPEE not in face.face.charToGlyph:
                continue
            pdfmetrics.registerFont(face)
            if bold and Path(bold).is_file():
                pdfmetrics.registerFont(TTFont("LFSans-Bold", bold))
                _FONTS = ("LFSans", "LFSans-Bold", True)
            else:
                # No bold cut: Paragraph's <b> would synthesise nothing, so the
                # bold style deliberately resolves to the regular face.
                _FONTS = ("LFSans", "LFSans", True)
            break
        except Exception:  # noqa: BLE001 - an unusable font is not a failed report
            continue
    return _FONTS


def _txt(s: str, unicode_ok: bool) -> str:
    """Escape for Paragraph's mini-HTML, and de-Unicode when the font can't."""
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if not unicode_ok:
        s = (s.replace("₹", "Rs.").replace("↔", "<->").replace("·", "-")
              .replace("—", "-").replace("“", '"').replace("”", '"')
              .replace("•", "-").replace("→", "->"))
    return s.replace("\n", "<br/>")


def build_recon_pdf(s: ReconSummary) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                    Paragraph, Spacer, Table, TableStyle)

    regular, bold, uni = _fonts()
    page = landscape(A4)
    margin = 14 * mm

    body = ParagraphStyle("body", fontName=regular, fontSize=7.4, leading=9.4,
                          textColor=colors.HexColor("#1F2937"))
    right = ParagraphStyle("right", parent=body, alignment=TA_RIGHT,
                           fontName=regular)
    head = ParagraphStyle("head", parent=body, fontName=bold, fontSize=7.2,
                          textColor=colors.white)
    head_r = ParagraphStyle("head_r", parent=head, alignment=TA_RIGHT)
    muted = ParagraphStyle("muted", parent=body, fontSize=7.2,
                           textColor=colors.HexColor("#6B7280"))

    def P(text, style=body):
        return Paragraph(_txt(text, uni), style)

    story = [
        Paragraph(_txt("GST Reconciliation Report", uni),
                  ParagraphStyle("t", fontName=bold, fontSize=15, leading=18,
                                 textColor=colors.HexColor("#111827"))),
        Spacer(1, 7),
    ]

    meta = _meta(s)
    meta_rows = [[P(k, muted), P(v)] for k, v in meta]
    meta_tbl = Table(meta_rows, colWidths=[80, 300], hAlign="LEFT")
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TEXTCOLOR", (1, len(meta) - 1), (1, len(meta) - 1),
         colors.HexColor("#B42318") if s.itc_at_risk else colors.HexColor("#067647")),
        ("FONTNAME", (1, len(meta) - 1), (1, len(meta) - 1), bold),
    ]))
    story += [meta_tbl, Spacer(1, 11)]

    if not s.lines:
        story.append(P("Nothing to reconcile — import a GSTR-2A workbook alongside "
                       "the purchase invoices and run the reconciliation again.", muted))
    else:
        data = [[Paragraph(_txt(h, uni), head_r if h in ("Books tax", "2A tax", "Diff")
                           else head) for h, _, _ in _COLUMNS]]
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        tints = {"only_in_books": "#FDE7E9", "value_mismatch": "#FFF4DA",
                 "only_in_2a": "#FFF9E6", "matched": "#EAF7F0"}
        inks = {"only_in_books": "#B42318", "value_mismatch": "#B54708",
                "only_in_2a": "#B54708", "matched": "#067647"}
        for n, line in enumerate(_sorted_lines(s), start=1):
            cells = _row(line)
            data.append([
                # Styled bold rather than wrapped in <b>: P() escapes its input,
                # so markup passed through it would print as literal tags.
                P(cells[0], ParagraphStyle(
                    f"st{n}", parent=body, fontName=bold,
                    textColor=colors.HexColor(inks.get(line.status, "#1F2937")))),
                P(cells[1]), P(cells[2]), P(cells[3]), P(cells[4]),
                P(inr(line.books_tax), right), P(inr(line.gstr2a_tax), right),
                P(inr(line.tax_diff) if line.tax_diff else "—", right),
                P(cells[8]), P(cells[9], muted),
            ])
            style.append(("BACKGROUND", (0, n), (0, n),
                          colors.HexColor(tints.get(line.status, "#FFFFFF"))))

        table = Table(data, colWidths=[w for _, _, w in _COLUMNS], repeatRows=1)
        table.setStyle(TableStyle(style))
        story.append(table)

    def _chrome(canvas, doc):
        """Footer on every page — the report leaves the office as an attachment,
        so it has to say whose it is and how many pages there are."""
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.setFillColor(colors.HexColor("#9CA3AF"))
        canvas.drawString(margin, 9 * mm, _txt(
            f"{COMPANY.name} · {COMPANY.gstin} · generated "
            f"{date.today().strftime('%d-%b-%Y')} by LedgerFlow", uni))
        canvas.drawRightString(page[0] - margin, 9 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
        canvas.line(margin, 12 * mm, page[0] - margin, 12 * mm)
        canvas.restoreState()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=page, leftMargin=margin, rightMargin=margin,
                          topMargin=margin, bottomMargin=17 * mm,
                          title=f"GST Reconciliation — {COMPANY.name}",
                          author="LedgerFlow")
    doc.addPageTemplates([PageTemplate(
        id="report",
        frames=[Frame(margin, 17 * mm, page[0] - 2 * margin,
                      page[1] - margin - 17 * mm, id="f")],
        onPage=_chrome)])
    doc.build(story)
    return buf.getvalue()
