# InvoiceOps

InvoiceOps is a local-first demonstration of administrative document intake, evidence-backed extraction, human review, approval, and delivery for a fictional small business. It is a portfolio project, not a complete accounting, tax, or fiscal system.

## Current verification status

- The local Docker stack (FastAPI, PostgreSQL, Redis, and a non-root Celery worker) has started successfully. PostgreSQL migrations were applied twice and `alembic check` reported no schema drift.
- The checks image runs Ruff, strict mypy, repeatable Alembic migration/drift checks, and unit/integration tests against real PostgreSQL and Redis/Celery. The image includes Tesseract; a bare Python environment without Tesseract is not equivalent.
- A real Redis/Celery worker processed synthetic text-PDF, scanned-PDF, PNG, and JPEG uploads asynchronously. The UI visibly labeled the structured output `DEMO — EXTRAÇÃO SIMULADA`; the parser/OCR was real, but the structured extraction was fixture-backed.
- Human correction, a new revision, approval, audit history, duplicate-upload detection, CSV/XLSX downloads, and delivery to the local test receiver were exercised. The receiver persisted one record, accepted an identical replay, and rejected a changed payload using the same idempotency key.
- The mobile review page was inspected in a browser at a 360-pixel viewport. Its evidence/review panels stack vertically and the document width remains within the viewport.
- The repository contains 24 independently generated synthetic base documents across four layout families, isolated ground truth, failure/duplicate derivatives, and a baseline-versus-model evaluator. No accuracy result is published because a real Ollama model has not run.
- **Real Ollama model extraction and n8n workflow activation remain unverified.** No model weights, real documents, paid APIs, or public application hosting were used.

See the [acceptance matrix](docs/acceptance.md), [test record](docs/testing.md), and [execution log](docs/progress.md) for evidence boundaries and remaining work.

## Run the local demonstration

Requirements: Docker Desktop with the Linux container engine and Docker Compose. The containers are pinned to specific image digests; the app container uses Python 3.12.

```powershell
.\scripts\demo.ps1
docker compose exec api uv run --no-sync python -m invoiceops.cli seed-demo
```

The seed command explicitly creates the local demonstration account and prints its generated password once. Save it locally; a later seed run does not reset or reveal an existing password. The script prints the loopback URL (normally port 8000; it selects the first free port through 8099 and records it in the ignored `.env`). The app only accepts the bundled synthetic files in demo mode and shows a clear simulation label.

Run the project checks with:

```powershell
.\scripts\test.ps1
```

This builds the checks image before running Ruff, strict mypy, and pytest. Do not use `docker compose down -v`: named database, queue, and upload volumes are persistent and contain the local demo state.

## Run real extraction

Install Ollama separately, pull a model deliberately after reviewing its size/license, and set the exact installed tag in the ignored `.env` file:

```powershell
# Edit only local ignored configuration; values here are examples, not a model recommendation.
(Get-Content .env) -replace '^INVOICEOPS_MODE=.*', 'INVOICEOPS_MODE=real' |
  Set-Content .env
(Get-Content .env) -replace '^OLLAMA_MODEL=.*', 'OLLAMA_MODEL=<exact-installed-tag>' |
  Set-Content .env
docker compose up -d --build --force-recreate api worker
```

Verify `http://127.0.0.1:8000/health/ready` before uploading a synthetic document. Real mode fails explicitly when the configured server/model is unavailable; it never falls back to demo fixtures.

## Modes and limitations

- `demo` mode combines the real PDF/image parser and OCR with fixed synthetic structured results. It is for workflow demonstration, not arbitrary-document extraction or AI evaluation.
- `real` mode requires a separately installed local Ollama server and an explicitly selected model. A model was not available during the recorded run; no Ollama end-to-end claim is made.
- All approvals are human. Export and webhook delivery are restricted to approved revisions. The local webhook receiver is a test target, not an ERP.
- Supported inputs in this implementation are PDF, PNG, and JPEG within configured limits. Arbitrary layouts, XML/NF-e, payments, tax advice, fiscal certification, and production compliance are out of scope.
- No distribution license has been selected. Use only synthetic sample files and do not upload real business documents to an unapproved provider.
- Aggregate Prometheus-format metrics are available at `/metrics`; request logs contain IDs, routes, status and duration, but no extracted document content.

## Project documentation

- [Architecture and state model](docs/architecture.md)
- [Technology decisions and evidence](docs/decisions.md)
- [Security controls and limitations](docs/security.md)
- [Acceptance matrix](docs/acceptance.md)
- [Extraction evaluation status](docs/evaluation.md)
- [Validation commands and results](docs/testing.md)
- [Execution log](docs/progress.md)
- [Demonstration script](docs/demo.md)
