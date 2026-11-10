# ADR-0011: Text-layer-first routing (cost/quota lever)

- **Status:** Accepted
- **Phase:** phase-0
- **Date:** 2026-11-10
- **Supersedes:** —
- **Superseded by:** —

## Context
At 20k invoices/day, Google is the dominant external cost (~$1,300–2,500/month estimated; see
architecture.md §5). Many B2B invoices are **digital PDFs with a real text layer** — they do not
need image OCR at all. v1 already has a PDF text-layer reader (PyMuPDF/`fitz`) as a fallback.

## Decision
In the extraction pipeline, **prefer the PDF text layer before OCR**. Route each document:
- **Digital PDF (reliable text layer)** → read text directly; skip Vision; send text-only to Gemini
  (no image tokens).
- **Scanned/image PDF or raster** → full path (rasterize → Vision → Gemini with image).

## Reasons
- **Biggest single cost/quota saving** (P9): digital invoices skip the Vision charge entirely and
  drop the Gemini image tokens (image/output tokens dominate cost).
- Also reduces latency and Vision quota pressure during bursts.
- Largely already built — it is a *reordering* of v1's existing readers (text-layer currently a
  fallback), not new capability (consistent with P5: behaviour of each reader unchanged).

## Alternatives considered
- **Always OCR (current v1 default ordering)** — simplest, uniform, but pays full Vision+image cost
  on every digital invoice; rejected on cost at scale.

## Consequences
- Need a reliable **"is the text layer trustworthy?"** check to avoid garbage-in on bad PDFs
  (fall back to OCR when the text layer is sparse/suspect).
- Realized savings depend on the **digital share** of real invoices — tracked as **H7** (currently
  estimated, not measured).
