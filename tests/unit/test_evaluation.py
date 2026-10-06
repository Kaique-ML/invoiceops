from __future__ import annotations

import pytest
from evals.run_evaluation import RESULTS, parse_baseline, run_evaluation, score_extraction

from invoiceops.domain.schemas import InvoiceExtraction, PageText


def test_baseline_handles_layout_aliases_and_does_not_guess_ambiguous_date() -> None:
    pages = [
        PageText(
            page=1,
            method="pdf-text",
            text=(
                "Document type: invoice\n"
                "Sold by: Nebula Fictional Supplies 01\n"
                "Business ID: 00.000.000/0003-01\n"
                "Receipt no.: C-001\n"
                "Issued: 03/04/2026\n"
                "Currency: EUR\n"
                "Amount due: € 151,45\n"
            ),
        )
    ]

    result = parse_baseline(pages)

    assert result.supplier == "Nebula Fictional Supplies 01"
    assert result.issue_date == "03/04/2026"
    assert result.total == "€ 151,45"


def test_score_counts_missing_values_and_detects_absent_field_hallucination() -> None:
    expected = {
        "supplier": "Cafe Aurora",
        "tax_identifier": None,
        "document_number": "A-001",
        "issue_date": None,
        "currency": "BRL",
        "subtotal": "100.00",
        "discounts": "0.00",
        "taxes": "0.00",
        "shipping": "0.00",
        "total": "100.00",
    }
    actual = InvoiceExtraction(
        supplier="  Cafe   Aurora ",
        tax_identifier="00.000.000/0001-00",
        document_number="A-001",
        issue_date=None,
        currency="brl",
        total="100.00",
    )

    score = score_extraction(actual, expected)

    assert score["critical_correct"] == 5
    assert score["critical_total"] == 6
    assert score["false_extractions_for_absent_fields"] == ["tax_identifier"]
    assert score["all_critical_correct"] is False


def test_evaluation_refuses_to_write_results_without_a_real_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "")

    with pytest.raises(RuntimeError, match="Real evaluation not run"):
        run_evaluation()

    assert not (RESULTS / "latest.json").exists()
