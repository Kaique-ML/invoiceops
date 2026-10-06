# Testing record

Updated 2026-10-05 (Windows / PowerShell 5.1 host, Linux Python 3.12 containers).

## Candidate validation

Command: `./scripts/test.ps1`. It builds the checks image and uses real PostgreSQL, Redis and Tesseract.

- Ruff 0.15.6: passed for `src`, `tests`, `scripts` and `evals`.
- mypy 1.19.1 strict mode: passed for 25 source files.
- Alembic 1.20.0: `upgrade head` passed twice; `alembic check` reported no new operations.
- pytest 9.1.1: **47 passed in 7.63 seconds**.
- `pip-audit 2.10.1 --strict`: no known vulnerabilities found.
- Candidate tracked-file scan: no credential assignment or private-key marker found; `.env`, `.venv` and tool caches were confirmed ignored.

The 47 tests include real OCR for text/image inputs, money/date ambiguity, evidence validation, one-repair model behavior, export sanitization, the 24-document dataset contract, evaluation scoring, approval/correction/audit, workspace and role isolation, exact-duplicate database constraint, durable outbox behavior under broker failure, aggregate metrics and a real Redis/Celery worker consuming a JSON task.

## Previously exercised live flow

The local Compose application previously processed bundled synthetic text PDF, scanned PDF, PNG and JPEG asynchronously. The browser flow exercised correction, a new revision, approval, exact duplicate upload, CSV/XLSX downloads and delivery to the authenticated local receiver. An identical idempotency replay succeeded and a changed payload with the same key returned HTTP 409. A 360 px viewport had no horizontal overflow and stacked review panels.

This evidence uses real parser/OCR, PostgreSQL, Redis and Celery. Structured values in demo mode remain fixture-backed and visibly labelled. The browser screenshots were inspected in the earlier session but are not committed as artifacts.

## Not executed

- No Ollama model call, model benchmark or accuracy report.
- No n8n workflow import/activation/receipt.
- No destructive worker-kill test against the preserved local volumes.
- Remote GitHub Actions status is recorded only after publication.
