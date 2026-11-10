"""Infrastructure configuration for the server — the one platform-aware seam.

Everything here is *infra*: where the datastore lives, which browser origins may
call the API, whether OCR runs in-process or over HTTP, which LLM provider to
read with. It is read from the environment (12-factor, P2) so the same image
runs on any platform by changing env alone.

This is additive. It does NOT touch the accounting domain's own configuration:
the CA-client identity still lives in ``app.domain.config.COMPANY`` and is edited
through the clients API / ``ClientRepository`` exactly as in v1 — migrating that
is not in scope here (P5). Nothing consumes most of these fields until the API
and extractor are wired (A6/A7); ``ledgerflow_db`` is the one used now, by the
composition root to build the SQLite client repository.

Field -> env var is the upper-cased name (pydantic-settings, case-insensitive):
``LEDGERFLOW_DB``, ``CORS_ORIGINS``, ``OCR_MODE``, ``OCR_SERVICE_URL``,
``LLM_PROVIDER``.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Local default DB location: server/data/ledgerflow.db. On an ephemeral-FS host
# this is overridden (LEDGERFLOW_DB) to point at a mounted volume — see ADR-0007.
_DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "ledgerflow.db"


class Settings(BaseSettings):
    """Process-wide infra config, loaded once at the composition root (deps.py)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- persistence (ADR-0007) --------------------------------------------
    # SQLite file path. Kept a filesystem path (not a DATABASE_URL) because the
    # Phase-0 engine is SQLite; a Postgres move later is a new adapter, not a
    # settings change (P3).
    ledgerflow_db: str = str(_DEFAULT_DB)

    # --- API surface --------------------------------------------------------
    # Browser origins allowed to call the API. v1 served the React bundle from
    # the same origin (no CORS); v2's client is a separate deployable, so the
    # origins are configured and tightened from "*" here (plan item 2 / ADR-0009).
    # Comma-separated in the env; use `cors_origin_list` to read it.
    cors_origins: str = "http://localhost:3000"

    # --- OCR extraction (ADR-0004) -----------------------------------------
    # "in_process" runs the reading pipeline inside this server (Decision:
    # in-process first). "http" calls a split-out OCR service at
    # `ocr_service_url`. Selects the InvoiceExtractor adapter in deps.py (A7).
    ocr_mode: str = "in_process"
    ocr_service_url: str = ""

    # --- reading ------------------------------------------------------------
    # Which LLM reads the invoice. Forward config for the reader wiring (A7);
    # the reading pipeline keeps its own provider env until then.
    llm_provider: str = "gemini"

    @property
    def cors_origin_list(self) -> list[str]:
        """`cors_origins` as a list, splitting on commas and dropping blanks."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
