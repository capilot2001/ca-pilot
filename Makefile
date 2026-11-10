# LedgerFlow v2 — dev shortcuts.
# Targets fill out as migration modules land (A2–A8). Placeholders for now.

.PHONY: install dev test lint fmt

install:          ## Install backend deps
	pip install -r server/requirements.txt

dev:              ## Run the server locally (OCR in-process)
	# Three source roots on the path: repo root -> `shared`, server -> `app`,
	# services/ocr -> `reading` (same scheme as pyproject's pytest pythonpath).
	PYTHONPATH="$(CURDIR):$(CURDIR)/server:$(CURDIR)/services/ocr" \
		uvicorn app.main:app --reload --port 8000

test:             ## Run tests (added during migration)
	pytest

lint:             ## Lint (ruff config added later)
	ruff check .

fmt:              ## Format
	ruff format .
