# InvoiceOps execution log

Updated: 2026-10-05 (America/Manaus)

## Completed locally

1. Inspected Windows/PowerShell, the accidental user-home Git root, local instructions and available Python/Git/Docker/GitHub tooling. Created a project-local Git repository on `main`; the outer repository is untouched.
2. Verified the modular FastAPI/PostgreSQL/Redis/Celery application, persistent private storage, real PDF/image OCR, explicit demo extraction, Ollama adapter, human review, audit, exports and webhook receiver.
3. Generated/validated 24 synthetic base documents across four layout families plus failure and duplicate derivatives. The evaluator refuses to publish results without a real configured model.
4. Fixed post-approval correction: it now creates a new review, revokes the current approval, preserves historical delivery records and excludes the revoked revision from current exports.
5. Added conservative same-workspace business-duplicate warnings, aggregate metrics, request duration/ID logs, real-service integration tests and pinned least-privilege CI.
6. Ran the Docker checks profile: Ruff passed, strict mypy passed, Alembic upgrade passed twice, drift check passed, and 47 tests passed. `pip-audit 2.10.1` found no known vulnerabilities. Candidate-file secret scanning found no credential assignment/private-key block.

## Evidence boundary

- Real components verified: PostgreSQL, Redis/Celery JSON task, Tesseract/PDFium OCR, PDF/image parsing, migrations, local receiver idempotency and server-rendered UI flow.
- Simulated: structured extraction in demo mode, explicitly labelled and restricted to bundled synthetic hashes.
- Blocked: real Ollama extraction/evaluation because no server/model is installed.
- Not run: n8n import/activation and receipt.

## Publication

GitHub owner authentication was verified as personal account `Kaique-ML`; `Kaique-ML/invoiceops` was absent before creation. Repository URL, commit SHA and CI conclusion are added after the remote verification step. No license has been selected.
