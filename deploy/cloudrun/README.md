# Cloud Run — the OCR service (post-migration)

Cloud Run is the intended home for the **OCR reading service** once it is split
out of the server (ADR-0004). In Phase-0 OCR runs **in-process** inside the
server (Decision: in-process first), so **there is no separate OCR container to
deploy yet** — this directory is a placeholder for that split, and its
Dockerfile lands with the `HttpExtractor` when the service is actually carved
out. Adding it now would be a new feature, not a migration.

Why Cloud Run for OCR when it exists:
- the reading job is CPU-spiky and stateless — it rasterizes, calls Vision, then
  Gemini — which fits Cloud Run's request-scoped autoscaling;
- **ADC needs no key file**: the runtime service account supplies credentials
  for Vision and Gemini automatically (grant it `roles/aiplatform.user` and
  Vision access). This is the `GOOGLE_APPLICATION_CREDENTIALS`-free path the env
  template refers to;
- `$PORT` is injected and the Dockerfile already binds it.

Until the split, the in-process server (SQLite volume) is better suited to
Railway — see `../railway/`. The server *can* run on Cloud Run too, but its
SQLite volume then needs a Cloud Run gen2 volume mount at `/data`.
