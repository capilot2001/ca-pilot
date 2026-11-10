"""LedgerFlow v2 — core API (server) entrypoint.

Skeleton app. It boots and serves a health check only; the real routes and wiring arrive in later
migration modules, logic unchanged from v1:

- A2  domain/ accounting core (models, classify, validate, masters, exporters)
- A3  services/ocr reading pipeline (imported in-process)
- A4  shared/ reading contract
- A5  ports + adapters + deps (composition root) + settings
- A6  API routes with v1 endpoint parity (/config, /clients, /extract, /export/*, ...)
- A7  wire InvoiceExtractor = InProcessExtractor
"""

from fastapi import FastAPI

app = FastAPI(title="LedgerFlow v2 — server", version="0.0.0")


@app.get("/api/health")
def health() -> dict:
    """Liveness probe. Expanded/kept through A6."""
    return {"status": "ok", "service": "server"}
