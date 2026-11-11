"""Composition root — where concrete adapters are chosen and wired to ports.

The rest of the server depends only on the *ports* (``ClientRepository``, and
later ``InvoiceExtractor`` / ``LLMInvoiceReader``); this one module knows which
adapter implements each, reads the infra config (``Settings``) that drives the
choice, and hands the API layer ready-made singletons through FastAPI's
``Depends``. Swapping SQLite for Postgres, or in-process OCR for an HTTP service,
is a change here and nowhere else (P3, ADR-0003).

Phase-0 A5a wires persistence. The extractor/reader ports join in A5b, and the
API starts consuming these providers in A6 (its lifespan calls
``get_client_repo().init()``, the equivalent of v1's ``store.init()``).
"""
from __future__ import annotations

from functools import lru_cache

from .adapters.extraction.in_process import InProcessExtractor
from .adapters.persistence.sqlite_client_repo import SqliteClientRepo
from .ports.client_repository import ClientRepository
from .ports.invoice_extractor import InvoiceExtractor
from .settings import Settings


@lru_cache
def get_settings() -> Settings:
    """Process-wide infra config, parsed once from the environment."""
    return Settings()


@lru_cache
def get_client_repo() -> ClientRepository:
    """The client store. SQLite in Phase-0 (ADR-0007); one instance per process,
    matching v1's single ``store`` module. The DB path comes from settings so the
    adapter stays free of environment lookups."""
    return SqliteClientRepo(db_path=get_settings().ledgerflow_db)


@lru_cache
def get_extractor() -> InvoiceExtractor:
    """The invoice extractor, selected by ``OCR_MODE`` (ADR-0004).

    "in_process" (the Phase-0 default, Decision: in-process first) runs the OCR
    reading pipeline inside this server. "http" would call a split-out OCR
    service at ``ocr_service_url`` — that adapter arrives when the service is
    actually split (post-migration), so it raises a clear error until then
    rather than pretend to exist."""
    mode = get_settings().ocr_mode
    if mode == "in_process":
        return InProcessExtractor()
    raise NotImplementedError(
        f"OCR_MODE={mode!r} is not available yet; the only Phase-0 extractor is "
        f"'in_process'. The HTTP extractor lands when the OCR service is split out.")
