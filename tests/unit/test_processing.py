from invoiceops.domain.schemas import PageText
from invoiceops.services.processing import _demo_extraction


def test_total_evidence_does_not_match_the_subtotal_label() -> None:
    extraction = _demo_extraction(
        [
            PageText(
                page=1,
                text="Subtotal: 100.00\nTotal: 100.00",
                method="pdf-text",
            )
        ]
    )

    total_reference = next(
        reference for reference in extraction.evidence if reference.field == "total"
    )
    assert total_reference.quote == "Total: 100.00"
