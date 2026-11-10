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

from .adapters.persistence.sqlite_client_repo import SqliteClientRepo
from .ports.client_repository import ClientRepository
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
