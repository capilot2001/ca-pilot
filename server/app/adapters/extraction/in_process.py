"""In-process ``InvoiceExtractor``: run the OCR reading pipeline in this process.

Phase-0 default (Decision: in-process first). The reading pipeline lives in
``services/ocr`` and is imported directly — no network hop — so a deployment
that has not split OCR out still works. When OCR_MODE=http, ``deps.py`` selects
an ``HttpExtractor`` against a running OCR service instead; that adapter and the
service's HTTP surface are a later step (the OCR split is post-migration), so it
is deliberately absent here rather than stubbed.

The in-process import of ``reading`` is the same app<->reading coupling the
migration already carries as tech debt (TODO.local.md); it is severed when the
service is split and this adapter is swapped for ``HttpExtractor``.
"""
from __future__ import annotations

from typing import List

from reading.pipeline import read_file
from shared.models import Invoice


class InProcessExtractor:
    """``InvoiceExtractor`` backed by the reading pipeline, called in-process."""

    def extract(self, file_bytes: bytes, filename: str) -> List[Invoice]:
        return read_file(file_bytes, filename)
