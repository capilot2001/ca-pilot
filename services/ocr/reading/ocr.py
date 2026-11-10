"""Text extraction layer.

Strategy (per the user's flowchart -> "OCR Extraction"):
  * Every document -- scan, photo, or digital PDF -- is read by Google Cloud
    Vision. PDFs are rasterised page-by-page and sent as images.
  * A digital PDF's embedded text layer is read too, but only as a fallback for
    fields the OCR left blank. It is exact and free where it exists, and it is
    the reason a Vision miss on a born-digital invoice does not become a blank
    field on the voucher.

Vision replaced PaddleOCR here. It still produces visually reconstructed rows
for the parser, so nothing downstream changed -- but it boxes one *word* at a
time where Paddle returned whole line segments, so it gets its own row builder
(`_cluster_rows` + `_join_row`) rather than sharing `_rows_from_boxes` with the
PyMuPDF path. Moving the engine out of the container drops ~2 GB of
paddlepaddle/opencv from the image, the 30-60 s cold-start model download, and
the oneDNN crash that made every x86_64 (i.e. Cloud Run) scan fail.

DOCUMENT_TEXT_DETECTION is the dense-document model, not the sparse
TEXT_DETECTION one: invoices are dense tables and it is the variant tuned for
them.

Each page is deskewed before its rows are rebuilt -- see `_estimate_skew`. Row
clustering is the one step that a crooked scan breaks outright, and a paper
invoice that went through a phone camera or a sheet feeder is never square.

Auth is Application Default Credentials. On Cloud Run the runtime service
account supplies them with no configuration; locally run
`gcloud auth application-default login` (or point GOOGLE_APPLICATION_CREDENTIALS
at a key file). The project also needs `vision.googleapis.com` enabled.
"""
from __future__ import annotations

import io
import math
import os
import re
from typing import Iterator, List, NamedTuple

import fitz  # PyMuPDF

from app.domain.validate import validate_gstin

_CLIENT = None  # cached Vision client (one TLS channel, reused across requests)

_RASTER_DPI = 400           # 300 drops isolated glyphs -- a bare "3" in a
                            # serial-number column, and the gap inside a
                            # tightly-set GSTIN. A page is still under 1 MB.
_MAX_IMAGE_BYTES = 15_000_000   # Vision rejects a single image over 20 MB
_BATCH_MAX_IMAGES = 5           # it allows 16 per call; 5 keeps us well inside
_BATCH_MAX_BYTES = 12_000_000   # ... the ~20 MB total-payload ceiling
_COL_GAP = 0.75             # a gap this many text-heights wide = a column break
_ROW_TOL = 0.4              # ...and this much baseline drift is still one row


def _rows_from_boxes(boxes, y_tol: float = 6.0):
    """boxes: list of (x, y, text). Cluster into visual rows by y, sort x within
    a row, and join with spaces. Returns reconstructed text (one line per row)."""
    boxes = [b for b in boxes if b[2] and b[2].strip()]
    boxes.sort(key=lambda b: (b[1], b[0]))
    rows = []
    cur, cur_y = [], None
    for x, y, t in boxes:
        if cur_y is None or abs(y - cur_y) <= y_tol:
            cur.append((x, t))
            cur_y = y if cur_y is None else (cur_y + y) / 2
        else:
            rows.append(cur)
            cur, cur_y = [(x, t)], y
    if cur:
        rows.append(cur)
    out = []
    for row in rows:
        row.sort(key=lambda p: p[0])
        out.append("  ".join(t.strip() for _, t in row))
    return "\n".join(out)


def _pdf_text_rows(doc: "fitz.Document") -> List[str]:
    """Reconstruct visual rows from a digital PDF's text layer, page by page."""
    pages = []
    for page in doc:
        words = page.get_text("words")  # (x0,y0,x1,y1, word, block, line, wordno)
        boxes = [(w[0], w[1], w[4]) for w in words]
        pages.append(_rows_from_boxes(boxes))
    return pages


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        from google.cloud import vision  # imported lazily on first real use
        try:
            _CLIENT = vision.ImageAnnotatorClient()
        except Exception as exc:  # noqa: BLE001 - re-raised with a usable message
            raise RuntimeError(
                "Google Cloud Vision credentials are unavailable. On Cloud Run "
                "the service's runtime account provides them; locally run "
                "'gcloud auth application-default login' or set "
                f"GOOGLE_APPLICATION_CREDENTIALS. ({exc})") from exc
    return _CLIENT


class _Word(NamedTuple):
    """One word box from Vision.

    `spaced` carries Vision's own detected_break -- whether a space follows this
    word. It is the only reliable separator signal, because Vision splits a
    token at punctuation into separate boxes ("MI", "-", "SALES", "/", "124")
    that must be re-joined with nothing between them. Geometry cannot tell those
    apart from real words: on a sample invoice the gap before "May" in
    "28-May-26" measured 0.29 text-heights while the genuine space in "Mamta
    Industries" measured 0.50.
    """
    x0: float
    y0: float
    x1: float
    y1: float
    spaced: bool
    text: str


def _boxes_from_annotation(annotation) -> List[_Word]:
    """Walk Vision's page -> block -> paragraph -> word tree into flat boxes."""
    from google.cloud import vision

    breaks = vision.TextAnnotation.DetectedBreak.BreakType
    # LINE_BREAK/EOL count as spacing: they end a Vision line, and any word that
    # follows on the same visual row is a different column anyway.
    spacing = {breaks.SPACE, breaks.SURE_SPACE, breaks.EOL_SURE_SPACE,
               breaks.LINE_BREAK}

    words: List[_Word] = []
    for page in annotation.pages:
        for block in page.blocks:
            for para in block.paragraphs:
                for word in para.words:
                    text = "".join(s.text for s in word.symbols)
                    verts = word.bounding_box.vertices
                    if not text.strip() or not verts:
                        continue
                    xs = [v.x for v in verts]
                    ys = [v.y for v in verts]
                    words.append(_Word(
                        float(min(xs)), float(min(ys)),
                        float(max(xs)), float(max(ys)),
                        word.symbols[-1].property.detected_break.type_ in spacing,
                        text))
    return words


# --- page skew -------------------------------------------------------------
# A paper invoice photographed on a phone or pulled through a sheet feeder is
# never square, and row clustering is the one step that a tilt breaks outright:
# _cluster_rows groups strictly by Y, so on a 1.3 deg page the Amount column
# lands ~55 px above the serial number in the same printed row (400 DPI, 3300 px
# wide) -- four times the row tolerance. The row then splits, the item table
# loses its figures, and the invoice extracts with a taxable value of zero.
_SKEW_LIMIT = 6.0     # degrees searched either side of upright
_SKEW_COARSE = 0.25   # first pass step
_SKEW_FINE = 0.02     # second pass step, +/- one coarse step around the peak
_SKEW_MIN = 0.1       # below this, rotating costs more than it fixes


def _skew_score(cells, deg: float, bin_h: float) -> float:
    """How sharply the page's word mass stacks into rows at this angle.

    The horizontal projection of a correctly-rotated page is a comb: dense
    where the text lines are, empty between them. Sum-of-squares rewards that
    concentration, so the angle maximising it is the page's own. Mass is the
    word's width (a long word is stronger evidence of a baseline than a stray
    speck) and is split across two bins by linear interpolation, without which
    the score jumps whenever a row happens to straddle a bin boundary.
    """
    s, c = math.sin(math.radians(deg)), math.cos(math.radians(deg))
    hist: dict = {}
    for xc, yc, mass in cells:
        f = (-xc * s + yc * c) / bin_h
        b = math.floor(f)
        frac = f - b
        hist[b] = hist.get(b, 0.0) + mass * (1.0 - frac)
        hist[b + 1] = hist.get(b + 1, 0.0) + mass * frac
    return sum(v * v for v in hist.values())


def _estimate_skew(words: List[_Word]) -> float:
    """The page's rotation in degrees (positive = text runs downhill to the
    right), by projection profile over the whole page.

    Vision's own per-word quads carry an angle, but a word is too short a
    baseline to measure one from: on the sample that motivated this, their
    median read -1.25 deg against a true -1.29 while the quartiles spanned
    -2.0 to -0.5. The page as a whole is the only stable ruler.

    Searched coarse-then-fine because the score has to be recomputed over every
    word at every candidate angle, and a full 0.02 deg sweep of +/-6 deg is 600
    passes for the same answer as ~35.
    """
    if len(words) < 8:
        return 0.0
    heights = sorted(w.y1 - w.y0 for w in words)
    bin_h = (heights[len(heights) // 2] or 20.0) / 2
    cells = [((w.x0 + w.x1) / 2, (w.y0 + w.y1) / 2, w.x1 - w.x0) for w in words]

    def sweep(lo: float, hi: float, step: float) -> float:
        best, best_score = lo, -1.0
        for k in range(int(round((hi - lo) / step)) + 1):
            deg = lo + k * step
            score = _skew_score(cells, deg, bin_h)
            if score > best_score:
                best, best_score = deg, score
        return best

    coarse = sweep(-_SKEW_LIMIT, _SKEW_LIMIT, _SKEW_COARSE)
    return sweep(coarse - _SKEW_COARSE, coarse + _SKEW_COARSE, _SKEW_FINE)


def _deskew(words: List[_Word]) -> List[_Word]:
    """Rotate the word boxes back to upright.

    Only the box centre is rotated; width and height are carried across
    unchanged. The boxes are axis-aligned rectangles already (Vision's quad
    collapsed to its extremes in _boxes_from_annotation), so rotating their
    corners would only inflate them, and at these angles the true change in
    extent is under a pixel.
    """
    deg = _estimate_skew(words)
    if abs(deg) < _SKEW_MIN:
        return words
    s, c = math.sin(math.radians(deg)), math.cos(math.radians(deg))
    out = []
    for w in words:
        xc, yc = (w.x0 + w.x1) / 2, (w.y0 + w.y1) / 2
        hw, hh = (w.x1 - w.x0) / 2, (w.y1 - w.y0) / 2
        nx, ny = xc * c + yc * s, -xc * s + yc * c
        out.append(_Word(nx - hw, ny - hh, nx + hw, ny + hh, w.spaced, w.text))
    return out


def _cluster_rows(words: List[_Word], y_tol: float = 0.0) -> List[List[_Word]]:
    """Group word boxes into visual rows by Y, each sorted left to right.

    The tolerance is a fraction of the page's own text height, not a pixel
    count: pixels depend on _RASTER_DPI, so a fixed one silently tightens the
    moment the raster gets sharper. _ROW_TOL of a text height is about the most
    a baseline shifts inside one printed row -- enough that a row label set
    slightly low beside its figures ("Total" against "55,600.000") still
    clusters with them instead of becoming a row of its own.
    """
    words = [w for w in words if w.text.strip()]
    if not words:
        return []
    if not y_tol:
        heights = sorted(w.y1 - w.y0 for w in words)
        y_tol = _ROW_TOL * (heights[len(heights) // 2] or 20.0)
    words.sort(key=lambda w: (w.y0, w.x0))
    rows: List[List[_Word]] = []
    cur: List[_Word] = []
    cur_y = None
    for w in words:
        if cur_y is None or abs(w.y0 - cur_y) <= y_tol:
            cur.append(w)
            cur_y = w.y0 if cur_y is None else (cur_y + w.y0) / 2
        else:
            rows.append(cur)
            cur, cur_y = [w], w.y0
    if cur:
        rows.append(cur)
    for row in rows:
        row.sort(key=lambda w: w.x0)
    return rows


def _row_height(row: List[_Word]) -> float:
    heights = sorted(w.y1 - w.y0 for w in row)
    return heights[len(heights) // 2] or 1.0


def _join_row(row: List[_Word]) -> str:
    """Join one row's words.

    The join has three outcomes instead of one, and that matters: Vision boxes
    one *word* at a time where PaddleOCR returned whole line segments, and the
    parser reads a run of 2+ spaces as a column break (see _INLINE_LABEL and the
    place-of-supply regex in parser.py). Joining every pair with two spaces the
    way the PyMuPDF path does would turn each word gap into a phantom column and
    truncate multi-word values. So: a gap wider than _COL_GAP text-heights is a
    real gutter between table columns and gets two spaces; otherwise Vision's
    own break flag decides one space or none.
    """
    height = _row_height(row)
    parts = [row[0].text.strip()]
    for prev, word in zip(row, row[1:]):
        if word.x0 - prev.x1 > _COL_GAP * height:
            parts.append("  ")
        elif prev.spaced:
            parts.append(" ")
        parts.append(word.text.strip())
    return "".join(parts)


# A label printed as a *column header*, with its value in the row below rather
# than beside it. `_parse_invoice_number` already reads the two shapes that
# survive reading-order text ("label: value" inline, and label alone with the
# value on the next line); this third shape only exists once the page has been
# laid back out in two dimensions, so it is resolved here, where the geometry
# is, and handed to the parser as a line it already understands.
_COLUMN_HEADERS = {
    "invoiceno": "Invoice No.",
    "billno": "Bill No.",
    "voucherno": "Voucher No.",
}
_COL_LABEL_MAX_WORDS = 3    # "Invoice No." is 2 boxes; "e-Way Bill No." is 4
_COL_VALUE_MAX_ROWS = 3     # a watermark row can sit between label and value


def _column_header_lines(rows: List[List[_Word]]) -> List[str]:
    """Emit "label: value" for each column header whose value sits below it.

    The value column is bounded on the left by the label's own left edge (a
    value is set flush with its header, give or take a fraction of a character)
    and on the right by wherever the *next* column starts on the header row.
    """
    out = []
    for i, row in enumerate(rows):
        height = _row_height(row)
        for k in range(len(row)):
            for n in range(1, min(_COL_LABEL_MAX_WORDS, len(row) - k) + 1):
                span = row[k:k + n]
                key = re.sub(r"[^a-z]", "", "".join(w.text for w in span).lower())
                label = _COLUMN_HEADERS.get(key)
                if not label:
                    continue
                left = span[0].x0
                right = _next_column_x(row, k + n, height)
                value = _value_below(rows, i, left - height / 2, right)
                if value:
                    out.append(f"{label}: {value}")
                break
    return out


def _next_column_x(row: List[_Word], start: int, height: float) -> float:
    """x of the first word after `start` that begins a new column."""
    for prev, word in zip(row[start - 1:], row[start:]):
        if word.x0 - prev.x1 > _COL_GAP * height:
            return word.x0
    return float("inf")


def _value_below(rows: List[List[_Word]], i: int,
                 left: float, right: float) -> str:
    """Text of the first row under `i` holding words inside [left, right)."""
    for row in rows[i + 1:i + 1 + _COL_VALUE_MAX_ROWS]:
        cell = [w for w in row if left <= w.x0 < right]
        if cell:
            return _join_row(cell).strip()
    return ""


def _page_text(words: List[_Word]) -> str:
    """One page of word boxes -> the reconstructed text the parser reads."""
    rows = _cluster_rows(_deskew(words))
    page = [_join_row(row) for row in rows]
    # resolved column headers ride at the end of their own page, where the
    # parser reads them in document order like any other line
    page += _column_header_lines(rows)
    return "\n".join(page)


def _batches(images: List[bytes]) -> Iterator[List[bytes]]:
    """Group encoded pages into requests that stay under Vision's per-call
    image-count and payload limits. An oversized page goes on its own."""
    cur: List[bytes] = []
    size = 0
    for data in images:
        if cur and (len(cur) >= _BATCH_MAX_IMAGES
                    or size + len(data) > _BATCH_MAX_BYTES):
            yield cur
            cur, size = [], 0
        cur.append(data)
        size += len(data)
    if cur:
        yield cur


def _annotate(images: List[bytes]) -> List[str]:
    """OCR encoded images, returning one reconstructed-rows string per image."""
    if not images:
        return []
    from google.cloud import vision

    client = _get_client()
    feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
    context = vision.ImageContext(language_hints=["en"])

    out: List[str] = []
    for batch in _batches(images):
        requests = [
            vision.AnnotateImageRequest(image=vision.Image(content=data),
                                        features=[feature],
                                        image_context=context)
            for data in batch
        ]
        for resp in client.batch_annotate_images(requests=requests).responses:
            # Per-image failures ride in the response, not as an exception.
            if resp.error.message:
                raise RuntimeError(
                    f"Cloud Vision could not read the page: {resp.error.message}")
            out.append(_page_text(
                _boxes_from_annotation(resp.full_text_annotation)))
    return out


_TOKEN = re.compile(r"[0-9A-Za-z]+")


def _repair_split_gstins(text: str) -> str:
    """Re-join a GSTIN that OCR broke into pieces.

    A tightly-set GSTIN can come back as "21 DIBPK1471D1ZX": Vision's break
    detector sees a gap between two glyph clusters and reports a space. The
    parser's GSTIN pattern then misses it, and a missing *supplier* GSTIN
    silently flips a purchase into a sale -- the one OCR slip in this pipeline
    that changes an invoice's meaning rather than just leaving a field blank.

    Only a run of 2-4 whitespace-separated tokens whose concatenation passes the
    full GSTIN check -- format, state code, embedded PAN, and the mod-36
    checksum -- is rewritten. That checksum is what makes the repair safe: two
    unrelated values that happen to sit side by side will not satisfy it.
    """
    out = []
    for line in text.splitlines():
        toks = list(_TOKEN.finditer(line))
        fixes = []
        i = 0
        while i < len(toks):
            joined = toks[i].group(0).upper()
            for j in range(i + 1, min(i + 4, len(toks))):
                # only a whitespace split counts as one OCR broke apart
                if line[toks[j - 1].end():toks[j].start()].strip():
                    break
                joined += toks[j].group(0).upper()
                if len(joined) > 15:
                    break
                if len(joined) == 15 and validate_gstin(joined)[0]:
                    fixes.append((toks[i].start(), toks[j].end(), joined))
                    i = j
                    break
            i += 1
        for start, end, value in reversed(fixes):
            line = line[:start] + value + line[end:]
        out.append(line)
    return "\n".join(out)


def _to_vision_image(img_bytes: bytes, ext: str) -> bytes:
    """Vision's images:annotate takes JPEG/PNG/GIF/BMP/WEBP/ICO/RAW but not
    TIFF -- that is files:annotate only -- so TIFFs are re-encoded to PNG."""
    if ext not in {".tif", ".tiff"}:
        return img_bytes
    from PIL import Image

    buf = io.BytesIO()
    Image.open(io.BytesIO(img_bytes)).convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _render_page(page) -> bytes:
    """PNG bytes for one PDF page, stepping the DPI down if a dense colour scan
    encodes larger than Vision will accept."""
    data = b""
    for dpi in (_RASTER_DPI, 200, 150):
        data = page.get_pixmap(dpi=dpi).tobytes("png")
        if len(data) <= _MAX_IMAGE_BYTES:
            break
    return data


def _ocr_pdf(doc: "fitz.Document"):
    """Rasterise each page and OCR them, batched into as few calls as fit.

    Returns (text per page, rendered PNG per page).
    """
    images = [_render_page(page) for page in doc]
    return _annotate(images), images


class Page(NamedTuple):
    """One page of a document, in the views the parser wants.

    rows   -> visually reconstructed rows (best for the item table).
    plain  -> the raw reading-order text (best for vertical label/value
              headers). For OCR output the two are the same.

    layer_rows/layer_plain are the same two views taken from a digital PDF's
    *embedded* text instead of from OCR. They are a fallback, not a result:
    Vision reads every file now, and the text layer is consulted only for
    fields the OCR left blank (see pipeline._fill_blanks).
    """
    rows: str
    plain: str
    layer_rows: str = ""
    layer_plain: str = ""
    # The rendered page, kept because the Gemini reader wants the picture and
    # not just the text (llm_extract). It was rasterised for Vision anyway, so
    # holding on to it costs nothing beyond the bytes.
    image: bytes = b""


class Extraction(NamedTuple):
    """What the OCR layer hands the pipeline.

    Pages stay separate rather than being joined here, because one uploaded
    file is not always one invoice -- a CA scans a stack of bills into a single
    PDF, and only a per-page view can tell where one ends and the next begins
    (see parser.split_documents). The pipeline joins the pages of each invoice
    it finds.
    """
    pages: List[Page]
    engine: str


def extract_text(file_bytes: bytes, filename: str) -> Extraction:
    """Read a document with Google Cloud Vision.

    Every file is OCR'd, digital PDFs included. They used to short-circuit to
    their embedded text layer, which is exact and free -- but it also meant the
    OCR engine never ran on the documents most invoices actually are, so any
    gap in the OCR path stayed invisible until a scan hit it. Vision is the one
    reader now; a text layer, where the PDF has one, is kept only to fill in
    what the OCR missed.
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        texts, images = _ocr_pdf(doc)
        rows = [_repair_split_gstins(t) for t in texts]
        layer_plain = [page.get_text() for page in doc]
        # A real text layer has plenty of alphanumerics; otherwise it's scanned
        # and page.get_text() is returning the handful of stray characters that
        # a scanner's own software sometimes leaves behind.
        if sum(c.isalnum() for c in "".join(layer_plain)) >= 40:
            layer_rows = _pdf_text_rows(doc)
            return Extraction(
                [Page(r, r, lr, lp, img) for r, lr, lp, img
                 in zip(rows, layer_rows, layer_plain, images)], "google-vision")
        return Extraction([Page(r, r, image=img)
                           for r, img in zip(rows, images)], "google-vision")

    # images
    if ext in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
        img = _to_vision_image(file_bytes, ext)
        rows = _repair_split_gstins("\n".join(_annotate([img])))
        return Extraction([Page(rows, rows, image=img)], "google-vision")

    # unknown -> best effort as image
    rows = _repair_split_gstins("\n".join(_annotate([file_bytes])))
    return Extraction([Page(rows, rows, image=file_bytes)], "google-vision")
