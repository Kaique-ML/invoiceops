from __future__ import annotations

from decimal import Decimal

from invoiceops.domain.money import SUPPORTED_CURRENCIES, parse_amount
from invoiceops.domain.schemas import InvoiceExtraction, PageText


def is_possible_business_duplicate(
    candidate: dict[str, object], existing: dict[str, object]
) -> bool:
    """Conservatively flag matching business identity; never discard either document."""
    required = ("document_number", "currency", "total")
    if any(not candidate.get(field) or not existing.get(field) for field in required):
        return False
    if any(str(candidate[field]) != str(existing[field]) for field in required):
        return False
    candidate_date = candidate.get("issue_date")
    existing_date = existing.get("issue_date")
    if candidate_date and existing_date and str(candidate_date) != str(existing_date):
        return False
    candidate_tax_id = candidate.get("tax_identifier")
    existing_tax_id = existing.get("tax_identifier")
    if candidate_tax_id and existing_tax_id:
        return str(candidate_tax_id).casefold() == str(existing_tax_id).casefold()
    candidate_supplier = candidate.get("supplier")
    existing_supplier = existing.get("supplier")
    return bool(
        candidate_supplier
        and existing_supplier
        and " ".join(str(candidate_supplier).casefold().split())
        == " ".join(str(existing_supplier).casefold().split())
    )


def validate_extraction(
    extraction: InvoiceExtraction,
    pages: list[PageText],
    *,
    manually_verified_fields: set[str] | None = None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    manual_fields = manually_verified_fields or set()
    page_text = {page.page: page.text.casefold() for page in pages}
    cited_fields = {reference.field for reference in extraction.evidence}

    for reference in extraction.evidence:
        source = page_text.get(reference.page)
        if reference.field in manual_fields:
            continue
        if source is None or reference.quote.casefold() not in source:
            issues.append(
                {
                    "code": "unverified_evidence",
                    "field": reference.field,
                    "message": "Source quote is not present on the cited page.",
                }
            )

    values = extraction.model_dump(exclude={"evidence", "items"})
    for field, value in values.items():
        if field == "document_type" and value == "unknown":
            continue
        if value is not None and field not in cited_fields and field not in manual_fields:
            issues.append(
                {
                    "code": "missing_evidence",
                    "field": field,
                    "message": "Extracted value has no source reference.",
                }
            )
    for index, item in enumerate(extraction.items):
        for field, value in item.model_dump().items():
            field_path = f"items[{index}].{field}"
            if (
                value is not None
                and field_path not in cited_fields
                and field_path not in manual_fields
            ):
                issues.append(
                    {
                        "code": "missing_evidence",
                        "field": field_path,
                        "message": "Extracted value has no source reference.",
                    }
                )

    if extraction.currency is not None and extraction.currency.upper() not in SUPPORTED_CURRENCIES:
        issues.append(
            {
                "code": "unsupported_currency",
                "field": "currency",
                "message": "Currency requires explicit review; no conversion was applied.",
            }
        )

    try:
        amounts = {
            field: parse_amount(getattr(extraction, field))
            for field in ("subtotal", "discounts", "taxes", "shipping", "total")
        }
    except ValueError:
        amounts = {}
        issues.append(
            {
                "code": "ambiguous_amount",
                "field": "amounts",
                "message": "At least one amount is invalid or ambiguous.",
            }
        )

    if amounts and extraction.tax_included_in_total is False:
        subtotal = amounts.get("subtotal")
        taxes = amounts.get("taxes")
        shipping = amounts.get("shipping")
        discounts = amounts.get("discounts")
        total = amounts.get("total")
        if all(
            value is not None
            for value in (subtotal, taxes, shipping, discounts, total)
        ):
            assert subtotal is not None
            assert taxes is not None
            assert shipping is not None
            assert discounts is not None
            assert total is not None
            expected = (
                subtotal + taxes + shipping - discounts
            )
            tolerance = Decimal("0.01")
            if abs(expected - total) > tolerance:
                issues.append(
                    {
                        "code": "total_mismatch",
                        "field": "total",
                        "message": (
                            "Explicitly declared components do not match the total within 0.01."
                        ),
                    }
                )
    return issues
