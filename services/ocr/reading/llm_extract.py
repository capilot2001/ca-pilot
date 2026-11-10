"""Read an invoice with Gemini, in the invoice's own vocabulary.

Why this exists
---------------
`parser.py` reads a page by matching captions and column positions. That works
until a template words something differently, and every new supplier is a new
template: an HSN printed 4 digits wide instead of 8, a "Taxable Amount" column
sitting beside a "Total Amount" one, a GST column that carries the tax rupees
and the rate together. Each is a one-line fix and there is no end to them --
the parser cannot generalise past the shapes it was written against, and a
missed column silently posts a voucher with the wrong taxable value.

A multimodal model reads the page the way the CA does, so it maps *whatever*
the invoice calls a column onto the fields we need. It is the primary reader
here; `parser.py` stays as the fallback for when the model is unavailable, and
as the source for any field the model leaves blank.

What it is NOT allowed to do
----------------------------
Only fields that are *printed on the page* come from the model. Direction,
nature of transaction, tax computation, ledger choice and the journal stay in
`classify.py`, derived from the company's own GSTIN -- those are accounting
decisions with one right answer, and handing them to a language model would put
an unreviewable guess inside a voucher. The model reads; the code decides.

Auth is the same Application Default Credentials that Cloud Vision uses (Vertex
AI, same project, no API key). `aiplatform.googleapis.com` must be enabled, and
the runtime service account needs `roles/aiplatform.user`. If any of that is
missing the reader turns itself off and the pipeline falls back to the parser,
so a credentials problem degrades the extraction instead of failing the upload.
"""
from __future__ import annotations

import io
import json
import logging
import os
import random
import re
import time
from typing import List, Optional

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

_GSTIN_SHAPE = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]")

_MODEL = os.environ.get("LEDGERFLOW_LLM_MODEL", "gemini-2.5-flash")
_LOCATION = os.environ.get("LEDGERFLOW_LLM_LOCATION", "global")
_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
# The reader is on by default; set 0/false to force the parser-only path (the
# regression suite does this so it stays hermetic and free).
_ENABLED = os.environ.get("LEDGERFLOW_LLM", "1").lower() not in ("0", "false", "no")

_CLIENT = None          # cached genai client
_DISABLED_REASON = ""   # set once the first call fails, to stop retrying

# Circuit breaker for sustained throttling. Retrying hard is right for one
# invoice, but a batch of 20 all retrying to exhaustion would spend longer than
# Cloud Run's request timeout and the user would get nothing at all instead of
# a batch with some invoices flagged. After this many invoices exhaust their
# retries back to back, the rest of the batch skips the model and is flagged;
# a success resets the count, and the breaker reopens on its own after the
# cooldown so a warm instance is not degraded for the rest of its life.
_MAX_CONSECUTIVE = 3
_COOLDOWN = 120.0
_consecutive = 0
_tripped_at = 0.0


# ---------------------------------------------------------------------------
# the shape we ask for
# ---------------------------------------------------------------------------
class LLMItem(BaseModel):
    """One row of the invoice's goods/services table."""
    description: str = ""
    hsn_sac: str = ""
    quantity: Optional[float] = None
    unit: str = ""
    rate: Optional[float] = None
    discount_percent: Optional[float] = None
    gst_rate_percent: Optional[float] = None
    taxable_value: Optional[float] = None


class LLMParty(BaseModel):
    name: str = ""
    gstin: str = ""
    address: str = ""
    pincode: str = ""
    state_name: str = ""
    state_code: str = ""


class LLMInvoice(BaseModel):
    """Everything the model is asked to read off the page.

    Supplier and buyer are returned as they are printed, NOT as "us" and
    "them": which one is the client is decided from the company GSTIN in
    `classify`, and asking the model to make that call would let a misread
    GSTIN flip a purchase into a sale.
    """
    invoice_number: str = ""
    invoice_date: str = Field(default="", description="ISO YYYY-MM-DD")
    supplier: LLMParty = Field(default_factory=LLMParty)
    buyer: LLMParty = Field(default_factory=LLMParty)
    place_of_supply_state_name: str = ""
    place_of_supply_state_code: str = ""
    items: List[LLMItem] = Field(default_factory=list)
    taxable_total: Optional[float] = None
    cgst_amount: Optional[float] = None
    sgst_amount: Optional[float] = None
    igst_amount: Optional[float] = None
    cess_amount: Optional[float] = None
    round_off: Optional[float] = None
    invoice_total: Optional[float] = None
    is_tax_invoice: bool = True
    notes: str = ""


_PROMPT = """You are reading an Indian GST tax invoice for a chartered accountant \
who will post it into TallyPrime. Extract exactly what is printed. Accuracy of \
the figures matters more than anything else.

Rules:

1. Read only what the document shows. If a field is not printed, leave it empty \
or null. Never infer, complete or "fix" a value -- a blank is reviewed, a \
guess is not. In particular never carry a value from one party to the other: \
if the supplier's address prints no PIN code, its pincode is empty even though \
the buyer's address has one.

2. `taxable_value` on every line is the amount BEFORE GST. Invoice templates \
vary: some print a "Taxable Amount" column next to an inclusive "Total \
Amount", some print only a gross "Amount". Where only a gross figure is \
printed, divide it out using that line's GST rate and return the net. The \
line's taxable values must add up to the invoice's taxable total.

3. `gst_rate_percent` is the COMBINED rate for the line: CGST 9% + SGST 9% is \
18. IGST 18% is 18. An exempt or nil-rated line is 0, not null. If the rate \
appears only in the HSN/SAC summary at the foot, take it from there and match \
it to the line by HSN.

4. `rate` is the per-unit price as printed, and `quantity` its count. Keep the \
unit ("BAG", "NOS", "Kgs") in `unit`.

5. `hsn_sac` is the digits only. Indian HSN codes are 4, 6 or 8 digits and SAC \
codes are 6 -- a 4-digit code like 2523 is valid and must not be discarded.

6. GSTINs are 15 characters. Copy them exactly; do not correct a checksum. \
The first two digits are the state code.

7. `invoice_date` is the invoice's OWN date. Ignore a purchase-order date, \
e-way-bill date, acknowledgement date or due date printed beside it.

8. `invoice_total` is the final payable figure, after any round-off.

9. Amounts are plain numbers: no currency symbol, no thousands separator. \
OCR renders the rupee sign inconsistently (as €, *, ? or a stray quote) -- \
ignore any such character glued to a figure.

10. If the page holds more than one invoice, read only the FIRST one.

The OCR text of the page is given below as a reading aid. Where it disagrees \
with the image, trust the image.

--- OCR TEXT ---
{ocr}
--- END OCR TEXT ---
"""


def model_name() -> str:
    """Short label for the engine string shown on the invoice card."""
    return _MODEL


def available() -> bool:
    """Whether the reader is switched on and has not already failed."""
    return _ENABLED and not _DISABLED_REASON


def _breaker_open() -> bool:
    """Whether sustained throttling has us skipping the model for now."""
    global _consecutive
    if _consecutive < _MAX_CONSECUTIVE:
        return False
    if time.time() - _tripped_at >= _COOLDOWN:
        _consecutive = 0            # cooled off; let the next invoice try
        return False
    return True


def _trip() -> None:
    global _consecutive, _tripped_at
    _consecutive += 1
    _tripped_at = time.time()
    if _consecutive == _MAX_CONSECUTIVE:
        log.warning("Gemini throttled on %d invoices in a row; the rest of "
                    "this batch will be read by the parser and flagged",
                    _consecutive)


def expected() -> bool:
    """Whether a caller had reason to expect a reading back.

    True while the reader is switched on and working, so that a None return
    means "this one invoice missed out" rather than "the reader is off here" —
    only the first deserves a note on the invoice.
    """
    return available()


def _project() -> str:
    """The GCP project to bill the call to.

    Cloud Run does not set GOOGLE_CLOUD_PROJECT, but ADC knows the project from
    the metadata server, so ask it rather than requiring the env var to be
    configured on the service.
    """
    if _PROJECT:
        return _PROJECT
    import google.auth

    return google.auth.default()[1] or ""


def _client():
    global _CLIENT
    if _CLIENT is None:
        from google import genai
        _CLIENT = genai.Client(vertexai=True, location=_LOCATION,
                               project=_project())
    return _CLIENT


# Gemini needs the mime type, and the same bytes were rendered for Vision
# (PNG) or uploaded by the user (anything). Sniff it rather than plumb it.
_MAGIC = ((b"\x89PNG", "image/png"), (b"\xff\xd8", "image/jpeg"),
          (b"GIF8", "image/gif"), (b"RIFF", "image/webp"),
          (b"BM", "image/bmp"), (b"%PDF", "application/pdf"))


def _mime(data: bytes) -> str:
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    return "image/png"


# Vision gets 400 DPI because it drops isolated small glyphs below that
# (_RASTER_DPI in ocr.py). Gemini does not need it: an A4 page at ~1600 px on
# the long side is ~140 DPI, comfortably legible, and about a sixth of the
# bytes. That matters for more than bandwidth -- a full-size page raster is
# what pushes a request into 429 RESOURCE_EXHAUSTED on Vertex's shared quota,
# and it is billed as input tokens either way.
_MAX_EDGE = 1600


def _fit(data: bytes) -> bytes:
    """Downscale a rendered page to something Gemini reads just as well."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        if max(img.size) <= _MAX_EDGE:
            return data
        scale = _MAX_EDGE / max(img.size)
        img = img.convert("RGB").resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
            Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:  # noqa: BLE001 - a page we can't resize is sent as it is
        return data


def _clean(value: str) -> str:
    """Empty out the placeholders a model reaches for instead of a blank."""
    v = (value or "").strip()
    return "" if v.lower() in ("null", "none", "n/a", "na", "-", "nil", "") else v


# Quota and availability blips: the same call may well succeed a moment later,
# so these are retried rather than taken as "the reader does not work here".
# Everything else (no SDK, API not enabled, service account without
# roles/aiplatform.user, a bad model name) fails identically every time.
_TRANSIENT = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "504",
              "DEADLINE_EXCEEDED", "500", "INTERNAL")
# Vertex's shared quota is the binding constraint on a project this size, and a
# 429 clears in tens of seconds rather than in one -- so a blip is worth
# waiting out, since falling back costs a wrong reading on an unfamiliar
# template where waiting costs only time. But only so far: these numbers are
# bounded by the fact that a whole batch shares ONE Cloud Run request, and a
# request that outlives the 900 s timeout returns nothing at all, which is
# strictly worse than a batch with some invoices flagged. Four attempts caps a
# throttled invoice near a minute; _MAX_CONSECUTIVE caps the batch.
_RETRIES = 4
_BACKOFF = 2.5          # seconds, doubled each attempt, plus jitter
_BACKOFF_CAP = 15.0


def _is_transient(exc: Exception) -> bool:
    text = str(exc)
    return any(t in text for t in _TRANSIENT)


def _disable(exc: Exception) -> None:
    """Turn the reader off for the life of the process.

    Only for a failure that cannot come good: a missing API, a service account
    without `roles/aiplatform.user`, a missing SDK. Retrying one of those once
    per page would add the model's timeout to every upload in the batch for no
    chance of a different answer. A quota blip is NOT one of these — disabling
    on the first 429 silently drops every remaining invoice in a batch back to
    the parser, which is exactly the failure this module exists to avoid.
    """
    global _DISABLED_REASON
    _DISABLED_REASON = str(exc)
    log.warning("Gemini invoice reader disabled for this process: %s", exc)


def read_invoice(images: List[bytes], ocr_text: str) -> Optional[LLMInvoice]:
    """Read one invoice's pages. Returns None if the model can't be reached.

    None is a normal outcome, not an error: the caller keeps the parser's
    reading and the upload succeeds either way.
    """
    global _consecutive
    if not available() or _breaker_open():
        return None
    try:
        from google.genai import types

        pages = [_fit(img) for img in images if img]
        parts = [types.Part.from_bytes(data=img, mime_type=_mime(img))
                 for img in pages]
        parts.append(types.Part.from_text(
            text=_PROMPT.format(ocr=(ocr_text or "")[:60_000])))
        contents = [types.Content(role="user", parts=parts)]
        config = types.GenerateContentConfig(
            # Zero temperature: the same invoice must read the same way twice,
            # or a CA re-running a batch gets different vouchers.
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=LLMInvoice,
        )
    except Exception as exc:  # noqa: BLE001 - degrade to the parser, never fail
        _disable(exc)
        return None

    resp = None
    for attempt in range(_RETRIES):
        try:
            resp = _client().models.generate_content(
                model=_MODEL, contents=contents, config=config)
            break
        except Exception as exc:  # noqa: BLE001
            if not _is_transient(exc):
                _disable(exc)
                return None
            if attempt == _RETRIES - 1:
                log.warning("Gemini unavailable after %d attempts (%s); this "
                            "invoice falls back to the parser", _RETRIES, exc)
                _trip()
                return None
            # Jittered, because a batch's invoices are read back to back and
            # lockstep retries would collide with each other all over again.
            delay = min(_BACKOFF * (2 ** attempt), _BACKOFF_CAP)
            time.sleep(delay * (0.5 + random.random()))

    _consecutive = 0
    try:
        parsed = resp.parsed
        if not isinstance(parsed, LLMInvoice):
            parsed = LLMInvoice.model_validate(json.loads(resp.text))
    except Exception as exc:  # noqa: BLE001 - a bad payload is not fatal either
        log.warning("Gemini returned an unusable payload: %s", exc)
        return None
    return _sanitise(parsed)


def _sanitise(r: LLMInvoice) -> LLMInvoice:
    """Normalise the string fields before anything downstream trusts them.

    A schema-constrained model still answers a blank string field with the
    word "null" often enough to matter, and "null" as a GSTIN would reach the
    checksum validator and be reported to the CA as an invalid registration.
    """
    for party in (r.supplier, r.buyer):
        party.name = _clean(party.name)
        party.address = _clean(party.address)
        party.state_name = _clean(party.state_name)
        party.state_code = _clean(party.state_code)

        # A GSTIN that isn't shaped like one is a misread, and letting it
        # through would overwrite the parser's good value and then be reported
        # to the CA as the supplier's invalid registration. A wrong CHECK DIGIT
        # is left alone on purpose -- that is a real defect on a real invoice
        # and classify() must surface it.
        gstin = _clean(party.gstin).upper()
        party.gstin = gstin if _GSTIN_SHAPE.fullmatch(gstin) else ""

        # The PIN has to be corroborated by the address the model itself
        # returned for this party. Asked for a field the invoice leaves blank,
        # the model reaches across to the other party's address for one -- an
        # invented PIN goes straight into the GSTR party block, where it is
        # both wrong and invisible.
        pin = _clean(party.pincode)
        party.pincode = pin if pin and pin in re.sub(r"\s", "", party.address) else ""
    r.invoice_number = _clean(r.invoice_number)
    r.invoice_date = _clean(r.invoice_date)
    r.place_of_supply_state_name = _clean(r.place_of_supply_state_name)
    r.place_of_supply_state_code = _clean(r.place_of_supply_state_code)
    for it in r.items:
        it.description = _clean(it.description)
        it.hsn_sac = re.sub(r"\D", "", _clean(it.hsn_sac))
        it.unit = _clean(it.unit)
    return r
