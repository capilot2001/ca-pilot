"""Reading-side port: the multimodal model that reads an invoice page.

The reading pipeline does not hardcode a provider — it reads through this
contract so the model can be swapped (LLM_PROVIDER) without touching the merge
logic. ``llm_extract`` is the in-process implementation (Gemini on Vertex AI)
and satisfies this Protocol structurally; ``pipeline.read_file`` takes it as its
default ``reader``.

This is the seam ADR-0010 names on the reading side ("the model reads"); the
server's own seam is ``app.ports.invoice_extractor.InvoiceExtractor`` ("the code
decides").
"""
from __future__ import annotations

from typing import List, Optional, Protocol

from .llm_extract import LLMInvoice


class LLMInvoiceReader(Protocol):
    """Reads one invoice's page images into an ``LLMInvoice``, or None.

    None is a normal outcome (the model was unreachable for this invoice); the
    caller keeps the parser's reading and the upload still succeeds.
    """

    def read_invoice(self, images: List[bytes], ocr_text: str) -> Optional[LLMInvoice]:
        """Read one invoice's pages; None if the model can't be reached."""
        ...

    def expected(self) -> bool:
        """Whether a caller had reason to expect a reading back (reader on + working)."""
        ...

    def model_name(self) -> str:
        """Short label for the engine string shown on the invoice card."""
        ...
