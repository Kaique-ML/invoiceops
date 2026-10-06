from __future__ import annotations

import hashlib
import re
from pathlib import Path

import httpx

from invoiceops.domain.money import parse_amount, serialize_amount
from invoiceops.domain.schemas import (
    InvoiceExtraction,
    PageText,
    ProcessingResult,
    SourceEvidence,
)
from invoiceops.domain.validation import validate_extraction
from invoiceops.extraction.documents import extract_pages
from invoiceops.providers.ollama_provider import (
    PROMPT_VERSION,
    OllamaStructuredProvider,
)
from invoiceops.settings import Settings

DEMO_SAMPLE_DIRECTORY = Path(__file__).resolve().parents[3] / "assets" / "demo"
DEMO_FIELDS = {
    "supplier": "Cafe Aurora Comercio Ficticio Ltda.",
    "tax_identifier": "00.000.000/0001-00",
    "document_number": "DEMO-2026-001",
    "issue_date": "2026-06-15",
    "currency": "BRL",
    "subtotal": "100.00",
    "discounts": "0.00",
    "taxes": "0.00",
    "shipping": "0.00",
    "total": "100.00",
}
DEMO_MARKERS = {
    "supplier": "Supplier:",
    "tax_identifier": "Tax ID:",
    "document_number": "Invoice number:",
    "issue_date": "Issue date:",
    "currency": "Currency:",
    "subtotal": "Subtotal:",
    "discounts": "Discounts:",
    "taxes": "Taxes:",
    "shipping": "Shipping:",
    "total": "Total:",
}


class RetryableExtractionError(RuntimeError):
    pass


class InvalidDemoDocumentError(ValueError):
    pass


def allowed_demo_hashes() -> set[str]:
    if not DEMO_SAMPLE_DIRECTORY.exists():
        return set()
    return {
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in DEMO_SAMPLE_DIRECTORY.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}
    }


def process_bytes(content: bytes, filename: str, settings: Settings) -> ProcessingResult:
    from invoiceops.extraction.documents import detect_document_type

    content_type = detect_document_type(content, filename)
    pages = extract_pages(
        content,
        content_type,
        max_pages=settings.max_pages,
        max_image_pixels=settings.max_image_pixels,
    )
    if settings.mode == "demo":
        digest = hashlib.sha256(content).hexdigest()
        if digest not in allowed_demo_hashes():
            raise InvalidDemoDocumentError(
                "Demo mode processes only the bundled synthetic sample files. "
                "Configure real mode with a local Ollama model for other documents."
            )
        extraction = _demo_extraction(pages)
        issues = validate_extraction(extraction, pages)
        return ProcessingResult(
            extraction=extraction,
            pages=pages,
            mode="demo",
            model=None,
            prompt_version="demo-fixture-v1",
            issues=issues,
        )

    try:
        extraction, model_name, issues = OllamaStructuredProvider(settings).extract(pages)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise RetryableExtractionError(
            "The configured local Ollama endpoint did not respond; a bounded retry is available."
        ) from exc
    return ProcessingResult(
        extraction=extraction,
        pages=pages,
        mode="ollama",
        model=model_name,
        prompt_version=PROMPT_VERSION,
        issues=issues,
    )


def _demo_extraction(pages: list[PageText]) -> InvoiceExtraction:
    references: list[SourceEvidence] = []
    document_type_quote = _find_quote(pages, "Invoice number:", "DEMO-2026-001")
    if document_type_quote is not None:
        page, text = document_type_quote
        references.append(SourceEvidence(field="document_type", page=page, quote=text))
    for field, value in DEMO_FIELDS.items():
        quote = _find_quote(pages, DEMO_MARKERS[field], value)
        if quote is not None:
            page, text = quote
            references.append(SourceEvidence(field=field, page=page, quote=text))
    item_quote = _find_quote(pages, "Line item:", "Coffee beans")
    items = []
    if item_quote is not None:
        page, text = item_quote
        references.append(SourceEvidence(field="items[0].description", page=page, quote=text))
        references.append(SourceEvidence(field="items[0].quantity", page=page, quote=text))
        references.append(SourceEvidence(field="items[0].line_total", page=page, quote=text))
        items = [{"description": "Coffee beans", "quantity": "1", "line_total": "100.00"}]
    tax_quote = _find_quote(pages, "Tax included:", "yes")
    tax_included: bool | None = None
    if tax_quote is not None:
        page, text = tax_quote
        references.append(SourceEvidence(field="tax_included_in_total", page=page, quote=text))
        tax_included = "yes" in text.casefold()
    return InvoiceExtraction(
        document_type="invoice",
        **DEMO_FIELDS,
        tax_included_in_total=tax_included,
        items=items,
        evidence=references,
    )


def _find_quote(pages: list[PageText], marker: str, value: str) -> tuple[int, str] | None:
    for page in pages:
        for line in page.text.splitlines():
            pattern = (
                rf"(?<![A-Za-z0-9]){re.escape(marker)}\s*"
                rf"{re.escape(value)}(?![A-Za-z0-9])"
            )
            if re.search(pattern, line, flags=re.IGNORECASE):
                quote = line.strip()
                if quote:
                    return page.page, quote[:500]
    return None


def normalize_extraction(
    extraction: InvoiceExtraction,
) -> tuple[dict[str, object], list[dict[str, str]]]:
    normalized = extraction.model_dump(mode="json")
    issues: list[dict[str, str]] = []
    currency = extraction.currency.upper() if extraction.currency else None
    normalized["currency"] = currency
    if extraction.issue_date is not None:
        from invoiceops.domain.dates import parse_issue_date

        try:
            parsed_date = parse_issue_date(extraction.issue_date)
        except ValueError:
            parsed_date = None
            issues.append(
                {
                    "code": "ambiguous_date",
                    "field": "issue_date",
                    "message": "Date needs human clarification.",
                }
            )
        normalized["issue_date"] = parsed_date.isoformat() if parsed_date else None

    for field in ("subtotal", "discounts", "taxes", "shipping", "total"):
        raw = getattr(extraction, field)
        try:
            normalized[field] = serialize_amount(parse_amount(raw))
        except ValueError:
            normalized[field] = None
            issues.append(
                {
                    "code": "ambiguous_amount",
                    "field": field,
                    "message": "Amount needs human clarification.",
                }
            )

    return normalized, issues
