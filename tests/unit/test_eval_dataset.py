from __future__ import annotations

import json
from pathlib import Path

import pytest
from pypdf import PdfReader
from pypdf.errors import PdfReadError

DATASET = Path(__file__).resolve().parents[2] / "evals" / "datasets"


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_base_dataset_has_separate_layout_family_splits_and_required_formats() -> None:
    development = _jsonl(DATASET / "development" / "manifest.jsonl")
    evaluation = _jsonl(DATASET / "evaluation" / "manifest.jsonl")
    development_families = {str(row["family"]) for row in development}
    evaluation_families = {str(row["family"]) for row in evaluation}
    all_rows = development + evaluation
    formats = [str(row["content_type"]) for row in all_rows]

    assert len(development) == len(evaluation) == 12
    assert len({row["sample_id"] for row in all_rows}) == 24
    assert development_families.isdisjoint(evaluation_families)
    assert len(development_families | evaluation_families) == 4
    assert formats.count("application/pdf") == 20
    assert formats.count("image/png") == 2
    assert formats.count("image/jpeg") == 2
    assert all("fields" not in row for row in all_rows)
    assert len(_jsonl(DATASET / "development" / "ground_truth.jsonl")) == 12
    assert len(_jsonl(DATASET / "evaluation" / "ground_truth.jsonl")) == 12


def test_dataset_contains_scan_multipage_rotated_ambiguous_and_derived_failures() -> None:
    scan = PdfReader(DATASET / "development" / "documents" / "layout_a-05.pdf")
    multipage = PdfReader(DATASET / "evaluation" / "documents" / "layout_c-02.pdf")
    rotated = PdfReader(DATASET / "evaluation" / "documents" / "layout_d-02.pdf")
    ambiguous_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(
            DATASET / "evaluation" / "documents" / "layout_c-01.pdf"
        ).pages
    )

    assert not (scan.pages[0].extract_text() or "").strip()
    assert len(multipage.pages) == 2
    assert rotated.pages[0].get("/Rotate") == 90
    assert "03/04/2026" in ambiguous_text
    assert PdfReader(DATASET / "derivatives" / "encrypted.pdf").is_encrypted
    with pytest.raises(PdfReadError):
        PdfReader(DATASET / "derivatives" / "corrupt.pdf")


def test_duplicate_derivatives_have_expected_identity_relationship() -> None:
    base = DATASET / "evaluation" / "documents" / "layout_c-01.pdf"
    exact = DATASET / "derivatives" / "layout_c-01.pdf"
    altered = DATASET / "derivatives" / "business_duplicate_different_bytes.pdf"

    assert base.read_bytes() == exact.read_bytes()
    assert base.read_bytes() != altered.read_bytes()
    assert PdfReader(base).pages[0].extract_text() == PdfReader(altered).pages[0].extract_text()
