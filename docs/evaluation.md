# Extraction evaluation

There are no measured model-extraction accuracy results yet. Do not interpret passing fixture tests or OCR compatibility as model accuracy.

The committed dataset contains 24 synthetic base documents: 12 development samples in layout families A/B and 12 held-out evaluation samples in families C/D. It covers text PDFs, image-only scans, PNG/JPEG, multiple pages, rotation, degraded quality, missing fields, ambiguous dates, divergent totals, exact duplicates, business-duplicate bytes, corrupt input and encrypted input. Ground truth is stored separately and is never read by the extraction pipeline.

`evals/run_evaluation.py` runs the same 12 held-out samples through a deterministic parser baseline and the configured Ollama provider, then applies shared normalization/scoring. It reports numerators/denominators for every field, false extraction of absent fields, complete critical-field records, review rate, failures and per-document timings. It refuses to write a result when `OLLAMA_MODEL` is absent, so there is no fabricated baseline-only comparison.

Run, after configuring real mode and an exact local model tag:

```powershell
docker compose exec worker uv run --no-sync python -m evals.run_evaluation
```

Status on 2026-10-05: **NOT_RUN** for model evaluation because no Ollama server/model was available. No `evals/results/latest.json` is claimed or committed.
