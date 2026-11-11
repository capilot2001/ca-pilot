"""Port: turn an uploaded file into invoice *readings* the server can classify.

This is the seam between the server ("the code decides") and the OCR reading
pipeline ("the model reads") — ADR-0004/0010. The server depends only on this
Protocol; whether reading happens in-process (``InProcessExtractor``) or over
HTTP against a split-out OCR service (``HttpExtractor``, post-migration) is
chosen in ``deps.py`` by ``OCR_MODE`` and invisible to callers (P3).

``extract`` returns *pre-classify* ``Invoice`` readings: printed fields read off
the page, with taxable values, tax, the journal and the final direction left for
``app.services.extraction`` to derive.
"""
from __future__ import annotations

from typing import List, Protocol

from shared.models import Invoice


class InvoiceExtractor(Protocol):
    """Reads one uploaded file into one pre-classify ``Invoice`` per bill."""

    def extract(self, file_bytes: bytes, filename: str) -> List[Invoice]:
        """Read ``file_bytes`` into pre-classify invoice readings."""
        ...
