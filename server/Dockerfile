# LedgerFlow v2 — server image (API + in-process OCR reading pipeline).
#
# THE BUILD CONTEXT IS THE REPO ROOT, not server/, because the server runs three
# path-based source roots in one process (Decision: in-process first):
#   shared/        -> `shared`   (the reading contract)
#   server/        -> `app`      (the core API + domain)
#   services/ocr/  -> `reading`  (the OCR reading pipeline, imported in-process)
#
# Build from the repo root:
#   docker build -f server/Dockerfile -t ledgerflow-server .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, for layer caching. In-process OCR means this image carries
# the reading stack too (PyMuPDF / Vision / Gemini / Pillow) — see
# server/requirements.txt.
COPY server/requirements.txt server/requirements.txt
RUN pip install -r server/requirements.txt

# The three source roots.
COPY shared/ shared/
COPY services/ocr/ services/ocr/
COPY server/ server/

# Path-based packaging — mirrors pyproject's pytest pythonpath and the Makefile
# `dev` target, so imports resolve identically in the container.
ENV PYTHONPATH=/app:/app/server:/app/services/ocr \
    OCR_MODE=in_process \
    LEDGERFLOW_DB=/data/ledgerflow.db

# SQLite lives on a mounted volume (ADR-0007). Declaring it means a plain
# `docker run` persists the client list, and platforms mount their volume here.
VOLUME ["/data"]

# $PORT is injected by Railway / Cloud Run; default 8000 for local runs.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
