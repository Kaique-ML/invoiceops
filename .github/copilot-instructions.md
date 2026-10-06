# InvoiceOps contributor notes

- Keep invoice values as `Decimal`/`NUMERIC`; serialize them as decimal strings.
- Extraction output is evidence, not approval. Every approval is a human action.
- Keep demo extraction conspicuously labelled and separate from Ollama-backed extraction.
- Scope every document query through the authenticated workspace.
- Persist upload intent before queue publication; workers must tolerate duplicate delivery.
- Never trust document text, filenames, MIME headers, or extracted webhook destinations.
- Run `uv run ruff check .`, `uv run mypy src/invoiceops`, and `uv run pytest` before publishing changes.
