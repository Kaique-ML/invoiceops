from __future__ import annotations

import json
import shutil
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "datasets"
FAMILIES = (
    ("layout_a", "development", "invoice", "Aurora"),
    ("layout_b", "development", "receipt", "Horizonte"),
    ("layout_c", "evaluation", "invoice", "Nebula"),
    ("layout_d", "evaluation", "purchase_order", "Orion"),
)
LABELS = {
    "layout_a": {
        "supplier": "Supplier",
        "tax_identifier": "Tax ID",
        "document_number": "Invoice number",
        "issue_date": "Issue date",
        "currency": "Currency",
        "subtotal": "Subtotal",
        "discounts": "Discounts",
        "taxes": "Taxes",
        "shipping": "Shipping",
        "total": "Total",
    },
    "layout_b": {
        "supplier": "Fornecedor",
        "tax_identifier": "CNPJ",
        "document_number": "Documento",
        "issue_date": "Emissão",
        "currency": "Moeda",
        "subtotal": "Produtos",
        "discounts": "Desconto",
        "taxes": "Tributos",
        "shipping": "Frete",
        "total": "Total a pagar",
    },
    "layout_c": {
        "supplier": "Sold by",
        "tax_identifier": "Business ID",
        "document_number": "Receipt no.",
        "issue_date": "Issued",
        "currency": "Currency",
        "subtotal": "Net amount",
        "discounts": "Less discount",
        "taxes": "Tax amount",
        "shipping": "Delivery",
        "total": "Amount due",
    },
    "layout_d": {
        "supplier": "Vendor",
        "tax_identifier": "Fiscal identifier",
        "document_number": "Order ID",
        "issue_date": "Date issued",
        "currency": "Currency",
        "subtotal": "Items subtotal",
        "discounts": "Rebate",
        "taxes": "Tax",
        "shipping": "Shipping charge",
        "total": "Grand total",
    },
}


def _format_amount(amount: Decimal, currency: str) -> str:
    formatted = f"{amount:,.2f}"
    if currency == "BRL":
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    if currency == "EUR":
        return "€ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return "$" + formatted


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _record(
    family_index: int,
    family: str,
    document_type: str,
    supplier_prefix: str,
    n: int,
) -> dict[str, Any]:
    currency = ("BRL", "USD", "EUR")[(family_index + n - 1) % 3]
    subtotal = Decimal(100 + family_index * 37 + n * 11) + Decimal("0.45")
    discounts = Decimal("0.00") if n % 2 else Decimal("2.15")
    taxes = Decimal("7.50") if n % 3 else Decimal("0.00")
    shipping = Decimal("4.25") if n % 2 else Decimal("0.00")
    total = subtotal - discounts + taxes + shipping
    if family == "layout_d" and n == 6:
        total += Decimal("1.00")

    document_number: str | None = f"{family[-1].upper()}-{n:03d}"
    if n == 4:
        document_number = None
    issue_date: str | None = f"2026-{family_index + 1:02d}-{n + 10:02d}"
    if family == "layout_c" and n == 1:
        issue_date = None
    currency_value: str | None = currency
    if family == "layout_d" and n == 5:
        currency_value = None

    return {
        "document_type": document_type,
        "supplier": f"{supplier_prefix} Fictional Supplies {n:02d}",
        "tax_identifier": None if n == 3 else f"00.000.000/000{family_index + 1}-{n:02d}",
        "document_number": document_number,
        "issue_date": issue_date,
        "currency": currency_value,
        "subtotal": f"{subtotal:.2f}",
        "discounts": f"{discounts:.2f}",
        "taxes": f"{taxes:.2f}",
        "shipping": f"{shipping:.2f}",
        "total": None if family == "layout_d" and n == 5 else f"{total:.2f}",
        "tax_included_in_total": False,
        "items": (
            [
                {
                    "description": f"Demonstration item {n:02d}",
                    "quantity": "2",
                    "unit_price": f"{(subtotal / 2):.2f}",
                    "line_total": f"{subtotal:.2f}",
                }
            ]
            if n % 2 == 0 or family == "layout_b"
            else []
        ),
        "_display_currency": currency,
        "_display_amounts": {
            "subtotal": subtotal,
            "discounts": discounts,
            "taxes": taxes,
            "shipping": shipping,
            "total": None if family == "layout_d" and n == 5 else total,
        },
        "_family": family,
        "_ambiguous_issue_date": family == "layout_c" and n == 1,
    }


def _lines(record: dict[str, Any], family: str) -> list[str]:
    labels = LABELS[family]
    lines = [
        "SYNTHETIC DEMONSTRATION - NOT A TAX DOCUMENT",
        f"Document type: {record['document_type']}",
        f"{labels['supplier']}: {record['supplier']}",
    ]
    for field in ("tax_identifier", "document_number", "issue_date", "currency"):
        value = record[field]
        ambiguous_date = field == "issue_date" and record["_ambiguous_issue_date"]
        if value is None and not ambiguous_date:
            continue
        shown = value
        if ambiguous_date:
            shown = "03/04/2026"
        lines.append(f"{labels[field]}: {shown}")
    for field, label in (
        ("subtotal", "subtotal"),
        ("discounts", "discounts"),
        ("taxes", "taxes"),
        ("shipping", "shipping"),
        ("total", "total"),
    ):
        amount = record["_display_amounts"][field]
        if amount is not None:
            lines.append(f"{labels[label]}: {_format_amount(amount, record['_display_currency'])}")
    lines.append("Tax included in total: no")
    for item in record["items"]:
        unit_price = _format_amount(Decimal(item["unit_price"]), record["_display_currency"])
        line_total = _format_amount(Decimal(item["line_total"]), record["_display_currency"])
        lines.append(
            f"Item: {item['description']} | Quantity: {item['quantity']} | "
            f"Unit price: {unit_price} | Line total: {line_total}"
        )
    return lines


def _write_pdf(lines: list[str], *, rotated: bool = False, two_pages: bool = False) -> bytes:
    buffer = BytesIO()
    document = Canvas(buffer, pagesize=A4, invariant=1)
    document.setTitle("Synthetic InvoiceOps evaluation sample")
    document.setAuthor("InvoiceOps synthetic dataset")
    if rotated:
        document.setPageRotation(90)
    _, height = A4
    first_page = lines[:9] if two_pages else lines
    second_page = lines[9:] if two_pages else []
    for index, line in enumerate(first_page):
        document.setFont("Helvetica", 10)
        document.drawString(42, height - 48 - index * 30, line[:110])
    if two_pages:
        document.showPage()
        for index, line in enumerate(second_page):
            document.setFont("Helvetica", 10)
            document.drawString(42, height - 48 - index * 30, line[:110])
    document.save()
    return buffer.getvalue()


def _raster(
    lines: list[str],
    family: str,
    *,
    low_quality: bool = False,
    rotated: bool = False,
) -> Image.Image:
    image = Image.new("RGB", (1500, 2600), "white")
    draw = ImageDraw.Draw(image)
    font = _font(30)
    for index, line in enumerate(lines):
        draw.text((90, 100 + index * 125), line[:75], fill="black", font=font)
    if rotated:
        image = image.rotate(180, expand=True)
    if low_quality:
        image = image.resize((500, 700)).convert("L")
        image = ImageEnhance.Contrast(image).enhance(0.45).filter(ImageFilter.GaussianBlur(0.8))
    return image


def _write_scan_pdf(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG", optimize=True)
    document = Canvas(buffer, pagesize=A4, invariant=1)
    document.setTitle("Synthetic scanned evaluation sample")
    document.drawImage(
        ImageReader(BytesIO(image_buffer.getvalue())),
        24,
        24,
        width=A4[0] - 48,
        height=A4[1] - 48,
        preserveAspectRatio=True,
        anchor="c",
    )
    document.save()
    return buffer.getvalue()


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )


def generate_dataset() -> int:
    manifests: dict[str, list[dict[str, Any]]] = {"development": [], "evaluation": []}
    ground_truth: dict[str, list[dict[str, Any]]] = {"development": [], "evaluation": []}
    base_files: dict[str, Path] = {}

    for family_index, (family, split, document_type, supplier_prefix) in enumerate(FAMILIES):
        document_directory = DATASET / split / "documents"
        document_directory.mkdir(parents=True, exist_ok=True)
        for n in range(1, 7):
            sample_id = f"{family}-{n:02d}"
            record = _record(family_index, family, document_type, supplier_prefix, n)
            lines = _lines(record, family)
            if n <= 4:
                content = _write_pdf(
                    lines,
                    rotated=family == "layout_d" and n == 2,
                    two_pages=family == "layout_c" and n == 2,
                )
                suffix = "pdf"
                content_type = "application/pdf"
            elif n == 5:
                content = _write_scan_pdf(
                    _raster(
                        lines,
                        family,
                        low_quality=family in {"layout_b", "layout_d"},
                        rotated=family == "layout_c",
                    )
                )
                suffix = "pdf"
                content_type = "application/pdf"
            else:
                image = _raster(lines, family)
                suffix = "png" if family in {"layout_a", "layout_c"} else "jpg"
                output = BytesIO()
                image.save(
                    output,
                    format="PNG" if suffix == "png" else "JPEG",
                    optimize=True,
                    **({"quality": 90} if suffix == "jpg" else {}),
                )
                content = output.getvalue()
                content_type = "image/png" if suffix == "png" else "image/jpeg"

            filename = f"{sample_id}.{suffix}"
            target = document_directory / filename
            target.write_bytes(content)
            relative_path = target.relative_to(DATASET).as_posix()
            manifests[split].append(
                {
                    "sample_id": sample_id,
                    "family": family,
                    "path": relative_path,
                    "content_type": content_type,
                }
            )
            labels = {key: value for key, value in record.items() if not key.startswith("_")}
            ground_truth[split].append({"sample_id": sample_id, "fields": labels})
            base_files[sample_id] = target

    for split in ("development", "evaluation"):
        _write_jsonl(DATASET / split / "manifest.jsonl", manifests[split])
        _write_jsonl(DATASET / split / "ground_truth.jsonl", ground_truth[split])

    derivatives = DATASET / "derivatives"
    derivatives.mkdir(parents=True, exist_ok=True)
    source = base_files["layout_c-01"]
    shutil.copyfile(source, derivatives / source.name)
    reader = PdfReader(str(source))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.add_metadata({"/Subject": "Synthetic formatting-only duplicate"})
    with (derivatives / "business_duplicate_different_bytes.pdf").open("wb") as stream:
        writer.write(stream)
    (derivatives / "corrupt.pdf").write_bytes(b"%PDF-1.7\nsynthetic malformed document\n")

    encrypted_writer = PdfWriter()
    encrypted_writer.add_blank_page(width=A4[0], height=A4[1])
    encrypted_writer.encrypt("synthetic-only")
    with (derivatives / "encrypted.pdf").open("wb") as stream:
        encrypted_writer.write(stream)
    _write_jsonl(
        derivatives / "manifest.jsonl",
        [
            {"path": source.name, "kind": "exact_duplicate", "of_sample_id": "layout_c-01"},
            {
                "path": "business_duplicate_different_bytes.pdf",
                "kind": "possible_business_duplicate",
                "of_sample_id": "layout_c-01",
            },
            {"path": "corrupt.pdf", "kind": "corrupt_input", "of_sample_id": None},
            {"path": "encrypted.pdf", "kind": "encrypted_input", "of_sample_id": None},
        ],
    )
    return sum(len(rows) for rows in manifests.values())


if __name__ == "__main__":
    count = generate_dataset()
    print(f"Generated {count} synthetic base documents in development/evaluation splits.")
