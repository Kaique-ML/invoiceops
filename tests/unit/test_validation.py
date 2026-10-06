from invoiceops.domain.schemas import InvoiceExtraction, PageText, SourceEvidence
from invoiceops.domain.validation import is_possible_business_duplicate, validate_extraction


def test_non_null_fields_require_real_page_quotes() -> None:
    pages = [PageText(page=1, text="Supplier: Cafe Aurora\nTotal: 12.00", method="pdf-text")]
    extraction = InvoiceExtraction(
        document_type="invoice",
        supplier="Cafe Aurora",
        total="12.00",
        currency="BRL",
        evidence=[
            SourceEvidence(field="supplier", page=1, quote="Supplier: Cafe Aurora"),
            SourceEvidence(field="total", page=1, quote="Total: 12.00"),
            SourceEvidence(field="currency", page=2, quote="Currency: BRL"),
        ],
    )
    issues = validate_extraction(extraction, pages)
    assert {issue["code"] for issue in issues} == {"missing_evidence", "unverified_evidence"}


def test_amount_equation_runs_only_when_tax_semantics_are_explicit() -> None:
    extraction = InvoiceExtraction(
        subtotal="10.00",
        discounts="0.00",
        taxes="2.00",
        shipping="0.00",
        total="10.00",
        tax_included_in_total=False,
    )
    assert any(issue["code"] == "total_mismatch" for issue in validate_extraction(extraction, []))
    extraction.tax_included_in_total = True
    assert not any(
        issue["code"] == "total_mismatch" for issue in validate_extraction(extraction, [])
    )
    extraction.tax_included_in_total = None
    assert not any(
        issue["code"] == "total_mismatch" for issue in validate_extraction(extraction, [])
    )


def test_business_duplicate_is_conservative_and_never_relies_on_one_field() -> None:
    first = {
        "supplier": "Cafe Aurora",
        "tax_identifier": "001234",
        "document_number": "00042",
        "issue_date": "2026-09-10",
        "currency": "BRL",
        "total": "123.45",
    }
    same_business_record = {**first, "supplier": "CAFE AURORA"}
    assert is_possible_business_duplicate(first, same_business_record)
    assert not is_possible_business_duplicate(first, {**same_business_record, "total": "123.46"})
    assert not is_possible_business_duplicate(
        {"document_number": "00042"}, {"document_number": "00042"}
    )
