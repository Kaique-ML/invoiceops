# Acceptance matrix

Updated 2026-10-05. `PASS` means the stated scope has direct execution evidence. `FAIL` means a requirement is not sufficiently implemented. `BLOCKED` needs an unavailable external component. `NOT_RUN` means implementation/artifacts exist but the stated execution has not occurred.

| Requirement | Implementation / evidence | Status |
|---|---|---|
| Isolated portfolio repository | A project-local Git repository on `main` is isolated from the unrelated user-home repository. `.env`, virtual environments, uploads and caches are ignored. Remote publication is recorded after push. | PASS |
| Python, OCR, schema and queue compatibility | Python 3.12 container; real Tesseract/PDFium OCR; Pydantic validation; JSON Celery task consumed through Redis. | PASS |
| PostgreSQL schema and migrations | Initial migration applied twice and `alembic check` found no drift. Integration-owned `invoiceops_n8n_*` tables are explicitly outside Alembic ownership. | PASS |
| Authentication, roles and workspace isolation | Session auth, CSRF, backend role checks and workspace-scoped object lookup are implemented. Real-PostgreSQL tests verify cross-workspace 404 and reader 403 behavior. | PASS |
| Durable asynchronous upload and extraction | Live Compose flow previously processed synthetic text PDF, scanned PDF, PNG and JPEG through API, outbox, Redis and Celery. Broker-failure persistence has a PostgreSQL integration test. Full killed-worker fault injection is not automated. | PASS |
| Structured demo extraction | Fixture-backed values are restricted to bundled hashes and visibly labelled `DEMO — EXTRAÇÃO SIMULADA`; parser/OCR evidence is real. | PASS |
| Real Ollama extraction | Adapter, strict schema and one repair attempt are implemented, but no installed server/model was available for an end-to-end call. | BLOCKED |
| Human review, correction, approval and audit | Version checks prevent stale writes. Corrections create revisions; post-approval correction revokes approval, resets current delivery state and preserves historical delivery rows. Tested with PostgreSQL. | PASS |
| Exact and possible business duplicates | Exact bytes use a workspace/hash constraint and avoid a second job. Conservative business matching creates a review warning only; conflicting known values prevent a match. | PASS |
| CSV/XLSX export | Only the current approved revision is exported. Identifiers are traceable, decimals retain numeric types, and formula-like text is neutralized. Live sample downloads and automated sanitization tests passed. | PASS |
| Authenticated webhook/idempotency | Durable delivery records, stable key, bounded retries and an authenticated local receiver are implemented. Same key/same payload replay succeeded; changed payload returned 409. | PASS |
| n8n workflow | Importable workflow and SQL schema exist, but import/credential activation and an end-to-end receipt were not executed. | NOT_RUN |
| Synthetic evaluation assets | 24 base documents in four separated layout families, derivatives, isolated gold files and a baseline/model evaluator are committed and structurally tested. | PASS |
| Real model evaluation and accuracy metrics | Evaluator refuses to produce results without `OLLAMA_MODEL`; no model result or accuracy claim exists. | BLOCKED |
| UI and responsive behavior | Login, list, upload, review, correction, approval, export, delivery and history are implemented in Portuguese. A prior browser run exercised the main flow and a 360 px layout; no screenshot is committed. | PASS |
| Observability | Health checks, aggregate Prometheus-format metrics and JSON request log messages provide request ID/status/duration without document content or high-cardinality metric labels. | PASS |
| Deterministic checks | Ruff, strict mypy, migration repeat/drift checks and 47 tests passed in the Docker checks profile with PostgreSQL, Redis/Celery and Tesseract. | PASS |
| Dependency and secret review | `pip-audit 2.10.1` reported no known vulnerabilities. A pre-commit candidate-file scan found no credential assignment or private-key marker; ignored paths were verified. | PASS |
| GitHub Actions | Least-privilege workflow pins verified action releases and runs static, migration, OCR, PostgreSQL and Redis/Celery checks. Remote run status is recorded after publication. | NOT_RUN |
| Public GitHub repository and matching SHA | Not populated until the final push/remote verification step. | NOT_RUN |
