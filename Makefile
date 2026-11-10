# LedgerFlow v2 — dev shortcuts.
# Targets fill out as migration modules land (A2–A8). Placeholders for now.

.PHONY: install dev test lint fmt

install:          ## Install backend deps
	pip install -r server/requirements.txt

dev:              ## Run the server locally (OCR in-process)
	cd server && uvicorn app.main:app --reload --port 8000

test:             ## Run tests (added during migration)
	pytest

lint:             ## Lint (ruff config added later)
	ruff check .

fmt:              ## Format
	ruff format .
