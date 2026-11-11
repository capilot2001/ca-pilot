"""LedgerFlow v2 — core API (server) entrypoint.

Reassembles the v1 FastAPI app under the v2 structure (A6): the routes and their
behaviour are v1's, but the app now wires its dependencies through the
composition root (``deps.py``) and its routes live in ``app.api`` routers.

Two changes from v1 beyond the restructure:
- the mounted React bundle is gone — the v2 client is a separate deployable
  (Next.js), so this service is API-only;
- CORS is configured from settings (tightened from "*") because the client is
  now a different origin.

OCR runs in-process for the migration (Decision: in-process first); the extract
endpoint reads through the ``InvoiceExtractor`` port, so splitting OCR out later
is a change in ``deps.py`` alone.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import clients, documents, exports
from .deps import get_client_repo, get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create/seed the client store and load the last-selected client.

    On startup rather than at import time so the modules stay importable
    (tests, tooling) without touching the filesystem — the v1 contract.
    """
    get_client_repo().init()
    yield


app = FastAPI(title="LedgerFlow v2 — server", version="0.1.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "service": "server"}


app.include_router(clients.router)
app.include_router(documents.router)
app.include_router(exports.router)
