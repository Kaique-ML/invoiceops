from pathlib import Path

import pytest

from invoiceops.extraction.documents import (
    DocumentLimitError,
    UnsupportedDocumentError,
    detect_document_type,
    extract_pages,
)
from invoiceops.services.processing import process_bytes
from invoiceops.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "assets" / "demo"


def test_mime_is_derived_from_extension_and_file_signature() -> None:
    assert detect_document_type(b"%PDF-1.4", "sample.pdf") == "application/pdf"
    assert detect_document_type(b"\x89PNG\r\n\x1a\n", "sample.png") == "image/png"
    with pytest.raises(UnsupportedDocumentError):
        detect_document_type(b"%PDF-1.4", "sample.png")


def test_pdf_text_and_scanned_pdf_use_distinct_real_paths() -> None:
    text_pdf = (SAMPLES / "synthetic_invoice.pdf").read_bytes()
    scan_pdf = (SAMPLES / "synthetic_scanned_invoice.pdf").read_bytes()
    text_pages = extract_pages(
        text_pdf,
        "application/pdf",
        max_pages=50,
        max_image_pixels=20_000_000,
    )
    scan_pages = extract_pages(
        scan_pdf,
        "application/pdf",
        max_pages=50,
        max_image_pixels=20_000_000,
    )
    assert text_pages[0].method == "pdf-text"
    assert "DEMO-2026-001" in text_pages[0].text
    assert scan_pages[0].method == "tesseract"
    assert "DEMO-2026-001" in scan_pages[0].text


@pytest.mark.parametrize("suffix", [".png", ".jpg"])
def test_images_use_real_ocr_and_demo_mode_is_explicit(suffix: str) -> None:
    content = (SAMPLES / f"synthetic_invoice{suffix}").read_bytes()
    content_type = "image/png" if suffix == ".png" else "image/jpeg"
    pages = extract_pages(
        content,
        content_type,
        max_pages=50,
        max_image_pixels=20_000_000,
    )
    assert pages[0].method == "tesseract"
    result = process_bytes(
        content,
        f"sample{suffix}",
        Settings(
            app_env="test",
            mode="demo",
            database_url="unused",
            redis_url="unused",
            session_secret="x" * 32,
            upload_dir=Path("uploads"),
            max_upload_bytes=10_000_000,
            max_pages=50,
            max_image_pixels=20_000_000,
            ollama_host="http://127.0.0.1:11434",
            ollama_model="",
            webhook_url="",
            webhook_secret="",
        ),
    )
    assert result.mode == "demo"
    assert result.extraction.document_number == "DEMO-2026-001"
    assert all(page.method == "tesseract" for page in result.pages)


def test_oversized_image_is_rejected_before_ocr() -> None:
    content = (SAMPLES / "synthetic_invoice.png").read_bytes()
    with pytest.raises(DocumentLimitError):
        extract_pages(content, "image/png", max_pages=50, max_image_pixels=100)
