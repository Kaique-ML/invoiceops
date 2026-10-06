# Architecture

InvoiceOps is intended to remain a modular monolith: FastAPI serves the server-rendered Portuguese UI and API, PostgreSQL stores business state, Redis transports JSON Celery messages, and a separate non-root worker handles parsing/OCR and structured extraction. Original files live in a private persistent volume.

## Evidence layers

1. Original bytes, SHA-256, size, and private generated storage key.
2. Parser/OCR page text with page number and extraction method.
3. Structured extraction result with model/mode metadata and quoted source references.
4. Human-corrected review revision and an immutable approval snapshot.

The demo provider is a fixed synthetic response and must say `DEMO — EXTRAÇÃO SIMULADA`. Real mode must fail with an actionable diagnostic when its OCR or Ollama dependency is missing; it must never fall back to fixtures.

## State dimensions

| Dimension | States | Owner |
|---|---|---|
| Processing | `queued`, `processing`, `completed`, `failed` | worker |
| Review | `pending`, `needs_review`, `approved`, `rejected` | reviewer |
| Delivery | `not_requested`, `pending`, `delivered`, `failed`, `unknown` | integration dispatcher |

Approval is allowed only after complete processing and an explicit human decision. A correction creates a revision, re-runs validation and invalidates approval of the edited revision; historical delivery records remain attached to the approved revision they delivered.

## Queue, idempotency and concurrency

Upload bytes, hash, document row and durable processing intent must commit before publication. Redis delivery is at-least-once; PostgreSQL constraints, claim/version checks and idempotent worker transitions provide correctness. A reconciler republishes pending intents and recovers stale leases. Celery early acknowledgement is documented by its stable task guide, so an acknowledged worker loss is handled by the reconciler rather than assuming broker redelivery.

Exact duplicates use `(workspace_id, sha256)` and return the existing record. Possible business duplicates require a matching document number, currency and total plus matching tax identifier (or normalized supplier); conflicting known dates prevent a match. They create a visible review warning only and never discard a document. All comparisons stay inside one workspace.

## Money, validation and exports

Amounts use `Decimal`/`NUMERIC`, with explicit two-place rules for BRL, USD and EUR and no FX conversion. Ambiguous `1.234` and `03/04/2026` remain unresolved. Arithmetic checks run only when component semantics (including whether tax is already in the total) are known. CSV/XLSX exports include approved revision identifiers and must neutralize untrusted text without changing numeric cell types.

## Limits and trade-offs

The first implementation targets PDF text, image-only/scanned PDFs, PNG and JPEG only. Limits are enforced before expensive parsing. OCR uses PDFium/Pillow and Tesseract; OCR does not provide document-wide confidence or invented bounding boxes. A model response is untrusted data. n8n is an optional local demo receiver, not an ERP.

`/metrics` exposes only aggregate state counts and processing duration totals. Request logs contain a correlation ID, method, path, response state and duration; document text and field values are excluded.
