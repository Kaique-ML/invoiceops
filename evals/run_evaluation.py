from __future__ import annotations

import json
import os
import platform
import re
import sys
import time
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from invoiceops.domain.dates import parse_issue_date
from invoiceops.domain.money import parse_amount
from invoiceops.domain.schemas import InvoiceExtraction, PageText
from invoiceops.domain.validation import validate_extraction
from invoiceops.extraction.documents import detect_document_type, extract_pages
from invoiceops.providers.ollama_provider import OllamaStructuredProvider
from invoiceops.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "datasets"
RESULTS = ROOT / "evals" / "results"
CRITICAL_FIELDS = (
    "supplier",
    "tax_identifier",
    "document_number",
    "issue_date",
    "currency",
    "total",
)
ALL_FIELDS = (
    "document_type",
    "supplier",
    "tax_identifier",
    "document_number",
    "issue_date",
    "currency",
    "subtotal",
    "discounts",
    "taxes",
    "shipping",
    "total",
    "tax_included_in_total",
    "items",
)
OPTIONAL_FIELDS = (
    "supplier",
    "tax_identifier",
    "document_number",
    "issue_date",
    "currency",
    "subtotal",
    "discounts",
    "taxes",
    "shipping",
    "total",
)
LABEL_ALIASES = {
    "supplier": ("supplier", "fornecedor", "sold by", "vendor"),
    "tax_identifier": ("tax id", "cnpj", "business id", "fiscal identifier"),
    "document_number": ("invoice number", "documento", "receipt no.", "order id"),
    "issue_date": ("issue date", "emissão", "issued", "date issued"),
    "currency": ("currency", "moeda"),
    "subtotal": ("subtotal", "produtos", "net amount", "items subtotal"),
    "discounts": ("discounts", "desconto", "less discount", "rebate"),
    "taxes": ("taxes", "tributos", "tax amount", "tax"),
    "shipping": ("shipping", "frete", "delivery", "shipping charge"),
    "total": ("total", "total a pagar", "amount due", "grand total"),
}


def _safe_host(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return "invalid-endpoint"
    hostname = parsed.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme}://{hostname}{port}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _field_lines(pages: list[PageText]) -> tuple[str, list[str]]:
    return "\n".join(page.text for page in pages), [
        line.strip() for page in pages for line in page.text.splitlines() if line.strip()
    ]


def parse_baseline(pages: list[PageText]) -> InvoiceExtraction:
    _, lines = _field_lines(pages)
    values: dict[str, str | None] = {field: None for field in OPTIONAL_FIELDS}
    evidence: list[dict[str, object]] = []
    items: list[dict[str, str | None]] = []
    tax_included: bool | None = None
    document_type: Literal["invoice", "receipt", "purchase_order", "unknown"] = "unknown"
    for page in pages:
        for line in page.text.splitlines():
            line = line.strip()
            if not line:
                continue
            type_match = re.match(
                r"^\s*document\s+type\s*:\s*(invoice|receipt|purchase_order)\s*$",
                line,
                re.I,
            )
            if type_match:
                match_value = type_match.group(1).lower()
                if match_value == "invoice":
                    document_type = "invoice"
                elif match_value == "receipt":
                    document_type = "receipt"
                elif match_value == "purchase_order":
                    document_type = "purchase_order"
                evidence.append(
                    {"field": "document_type", "page": page.page, "quote": line[:500]}
                )
            item_match = re.match(r"^\s*item\s*:\s*(.*?)\s*$", line, re.I)
            if item_match:
                item: dict[str, str | None] = {"description": None}
                parts = [part.strip() for part in item_match.group(1).split("|")]
                if parts and parts[0]:
                    item["description"] = parts[0]
                for part in parts[1:]:
                    key, separator, value = part.partition(":")
                    normalized_key = key.strip().casefold().replace(" ", "_")
                    field_name = {
                        "quantity": "quantity",
                        "unit_price": "unit_price",
                        "line_total": "line_total",
                    }.get(normalized_key)
                    if separator and field_name is not None:
                        item[field_name] = value.strip()
                item_index = len(items)
                items.append(item)
                for item_field, item_value in item.items():
                    if item_value is not None:
                        evidence.append(
                            {
                                "field": f"items[{item_index}].{item_field}",
                                "page": page.page,
                                "quote": line[:500],
                            }
                        )
            tax_match = re.match(r"^\s*tax included in total\s*:\s*(yes|no)\s*$", line, re.I)
            if tax_match:
                tax_included = tax_match.group(1).casefold() == "yes"
                evidence.append(
                    {
                        "field": "tax_included_in_total",
                        "page": page.page,
                        "quote": line[:500],
                    }
                )
            for field, aliases in LABEL_ALIASES.items():
                for label in aliases:
                    match = re.match(rf"^\s*{re.escape(label)}\s*:\s*(.*?)\s*$", line, re.I)
                    if match:
                        value = match.group(1).strip()
                        if value:
                            values[field] = value
                            evidence.append(
                                {"field": field, "page": page.page, "quote": line[:500]}
                            )
                        break
    currency = values["currency"]
    if currency and currency.upper() not in {"BRL", "USD", "EUR"}:
        currency = None
    values["currency"] = currency
    return InvoiceExtraction.model_validate(
        {
            "document_type": document_type,
            **values,
            "tax_included_in_total": tax_included,
            "items": items,
            "evidence": evidence,
        }
    )


def _canonical(field: str, value: object) -> str | None:
    if value is None:
        return None
    if field == "items":
        if not isinstance(value, list):
            return "!invalid"
        normalized_items: list[dict[str, str | None]] = []
        for item in value:
            if hasattr(item, "model_dump"):
                item = item.model_dump(mode="json")
            if not isinstance(item, Mapping):
                return "!invalid"
            normalized_item: dict[str, str | None] = {}
            for key in ("description", "quantity", "unit_price", "line_total"):
                item_value = item.get(key)
                normalized_item[key] = _canonical(
                    key if key in {"unit_price", "line_total"} else "text",
                    item_value,
                )
            normalized_items.append(normalized_item)
        return json.dumps(normalized_items, ensure_ascii=False, sort_keys=True)
    text = str(value).strip()
    if field in {"subtotal", "discounts", "taxes", "shipping", "total", "unit_price", "line_total"}:
        try:
            amount = parse_amount(text)
        except ValueError:
            return "!invalid"
        return str(amount) if amount is not None else None
    if field == "issue_date":
        try:
            return parse_issue_date(text).isoformat()
        except ValueError:
            return "!ambiguous"
    if field == "currency":
        return text.upper()
    if field == "tax_identifier":
        return "".join(character for character in text.upper() if character.isalnum())
    return " ".join(text.casefold().split())


def score_extraction(
    actual: InvoiceExtraction, expected: dict[str, object]
) -> dict[str, object]:
    fields = {
        field: _canonical(field, getattr(actual, field))
        == _canonical(field, expected.get(field))
        for field in ALL_FIELDS
    }
    false_absences = [
        field
        for field in OPTIONAL_FIELDS
        if expected.get(field) is None and getattr(actual, field) is not None
    ]
    expected_items = expected.get("items")
    if expected_items == [] and actual.items:
        false_absences.append("items")
    return {
        "critical_correct": sum(fields[field] for field in CRITICAL_FIELDS),
        "critical_total": len(CRITICAL_FIELDS),
        "all_critical_correct": all(fields[field] for field in CRITICAL_FIELDS),
        "all_fields_correct": sum(fields.values()),
        "false_extractions_for_absent_fields": false_absences,
        "field_correctness": fields,
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, object]:
    field_totals: Counter[str] = Counter()
    field_correct: Counter[str] = Counter()
    false_absences = Counter[str]()
    complete = 0
    review_needed = 0
    for row in rows:
        score = row["score"]
        assert isinstance(score, dict)
        correctness = score["field_correctness"]
        assert isinstance(correctness, dict)
        for field, correct in correctness.items():
            field_totals[field] += 1
            field_correct[field] += int(correct)
        for field in score["false_extractions_for_absent_fields"]:
            false_absences[field] += 1
        complete += int(score["all_critical_correct"])
        review_needed += int(row["review_needed"])
    return {
        "all_fields": {
            field: {
                "correct": field_correct[field],
                "total": field_totals[field],
                "rate": field_correct[field] / field_totals[field] if field_totals[field] else None,
            }
            for field in ALL_FIELDS
        },
        "critical_fields": {
            field: {
                "correct": field_correct[field],
                "total": field_totals[field],
                "rate": field_correct[field] / field_totals[field] if field_totals[field] else None,
            }
            for field in CRITICAL_FIELDS
        },
        "documents_all_critical_correct": {"correct": complete, "total": len(rows)},
        "false_extractions_when_expected_absent": dict(sorted(false_absences.items())),
        "review_needed": {"count": review_needed, "total": len(rows)},
        "document_durations_ms": [row["duration_ms"] for row in rows],
    }


def run_evaluation() -> Path:
    manifest = _read_jsonl(DATASET / "evaluation" / "manifest.jsonl")
    gold_rows = _read_jsonl(DATASET / "evaluation" / "ground_truth.jsonl")
    ground_truth = {row["sample_id"]: row["fields"] for row in gold_rows}
    if len(manifest) != 12 or len(ground_truth) != 12:
        raise ValueError("The evaluation split must contain the 12 held-out base samples.")
    settings = Settings.from_environment()
    if not settings.ollama_model:
        raise RuntimeError(
            "Real evaluation not run: set OLLAMA_MODEL to the exact installed local model tag."
        )
    provider = OllamaStructuredProvider(settings)
    baseline_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []

    for sample in manifest:
        sample_id = sample["sample_id"]
        content = (DATASET / sample["path"]).read_bytes()
        started = time.perf_counter()
        content_type = detect_document_type(content, sample["path"])
        pages = extract_pages(
            content,
            content_type,
            max_pages=settings.max_pages,
            max_image_pixels=settings.max_image_pixels,
        )
        parser_duration_ms = round((time.perf_counter() - started) * 1000, 2)
        expected = ground_truth[sample_id]

        baseline_started = time.perf_counter()
        baseline = parse_baseline(pages)
        baseline_duration = round((time.perf_counter() - baseline_started) * 1000, 2)
        baseline_issues = validate_extraction(baseline, pages)
        baseline_rows.append(
            {
                "sample_id": sample_id,
                "family": sample["family"],
                "score": score_extraction(baseline, expected),
                "review_needed": bool(baseline_issues)
                or any(getattr(baseline, field) is None for field in CRITICAL_FIELDS),
                "duration_ms": round(parser_duration_ms + baseline_duration, 2),
                "parser_duration_ms": parser_duration_ms,
                "issues": [issue["code"] for issue in baseline_issues],
            }
        )

        model_started = time.perf_counter()
        error: str | None = None
        model_name: str | None = None
        try:
            extraction, model_name, issues = provider.extract(pages)
        except Exception as exc:
            error = type(exc).__name__
            extraction = InvoiceExtraction()
            issues = [{"code": "model_error", "field": "document", "message": error}]
        model_duration = round((time.perf_counter() - model_started) * 1000, 2)
        model_rows.append(
            {
                "sample_id": sample_id,
                "family": sample["family"],
                "score": score_extraction(extraction, expected),
                "review_needed": bool(issues)
                or any(getattr(extraction, field) is None for field in CRITICAL_FIELDS),
                "duration_ms": round(parser_duration_ms + model_duration, 2),
                "parser_duration_ms": parser_duration_ms,
                "model_duration_ms": model_duration,
                "issues": [issue["code"] for issue in issues],
                "error": error,
            }
        )

    report = {
        "status": "completed",
        "executed_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "base_evaluation_documents": len(manifest),
            "families": sorted({row["family"] for row in manifest}),
            "development_families": ["layout_a", "layout_b"],
            "evaluation_families": ["layout_c", "layout_d"],
            "input_types": dict(
                sorted(Counter(str(row["content_type"]) for row in manifest).items())
            ),
            "document_types": dict(
                sorted(Counter(str(row["fields"]["document_type"]) for row in gold_rows).items())
            ),
        },
        "model": {
            "name": settings.ollama_model,
            "host": _safe_host(settings.ollama_host),
            "temperature": 0,
            "prompt_version": "invoice-extract-v1",
            "hardware": {
                "runtime_platform": platform.platform(),
                "logical_cpu_count": os.cpu_count(),
                "gpu": "Not inspected by this evaluator.",
                "container_memory": "Not measured by this evaluator.",
            },
        },
        "timing_note": (
            "First evaluation sample includes any cold start; no warm-up sample was discarded. "
            "Small-sample timings are descriptive, not statistically significant."
        ),
        "normalization": (
            "All contract fields are scored. Critical fields are supplier, tax identifier, "
            "document number, issue date, currency, and total. Monetary values use Decimal "
            "normalization; dates are parsed only when unambiguous. Missing optional fields count "
            "as correct only when both expected and actual are null."
        ),
        "review_policy": (
            "A sample is marked review-needed when validation reports an issue or any critical "
            "field is missing. This evaluator metric is conservative and does not authorize "
            "approval."
        ),
        "cold_start_sample_id": model_rows[0]["sample_id"] if model_rows else None,
        "baseline": {"summary": _aggregate(baseline_rows), "documents": baseline_rows},
        "model_pipeline": {"summary": _aggregate(model_rows), "documents": model_rows},
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    output = RESULTS / "latest.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    try:
        result_path = run_evaluation()
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error
    print(f"Evaluation report written to {result_path.relative_to(ROOT)}")
