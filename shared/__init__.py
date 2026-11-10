"""Shared contracts — data exchanged across LedgerFlow v2 service boundaries.

``shared.models`` is the single source of truth for the invoice/reading data
model (Invoice, LineItem, TaxBreakup, JournalLine, Assumption, Exception_, ...).
Both the server domain (which classifies) and the OCR reading pipeline (which
extracts) import these types from here, so the contract between them cannot
drift.

Seeded in migration module A4. The broader shared kernel (config / validate /
tax_heads), still in the server domain for now, moves here at the OCR service
split (see TODO.local.md).
"""
