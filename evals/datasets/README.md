# Synthetic evaluation dataset

Run `uv run --extra dev python scripts/make_eval_dataset.py` to regenerate this deterministic, wholly synthetic dataset. It contains 24 independent base documents: four layout families, six documents per family, 12 development documents and 12 held-out evaluation documents. The evaluation split contains two layout families not present in development.

Each split has a manifest and a separate `ground_truth.jsonl`; the document parser and extraction provider receive only document bytes/page text. Never use names, manifest labels, or ground truth to choose extracted values. The generated documents are clearly labelled synthetic, not tax documents.

The base set includes 16 text PDFs, four image-only scanned PDFs, two PNGs and two JPEGs. It includes multiple document types, documents with and without items, BRL/USD/EUR display formats, absent fields, an ambiguous date, a multi-page PDF, rotated pages, low-quality scans, and a divergent total. Derived files under `derivatives/` include an exact byte duplicate, a same-business-data PDF with different bytes, a corrupt PDF and an encrypted PDF. Derivatives are not counted in the 24 independent samples.

`evals/run_evaluation.py` compares a deterministic label parser with the real local Ollama structured-output provider using the same held-out samples and OCR pages. It refuses to run without an explicitly configured `OLLAMA_MODEL`; there is no fixture fallback. Any saved model results belong under the ignored `evals/results/` directory. No accuracy claim should be made until a complete real run has generated `evals/results/latest.json`.
