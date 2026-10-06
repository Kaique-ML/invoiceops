from __future__ import annotations

from io import BytesIO

import pypdfium2 as pdfium
import pytesseract
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from invoiceops.domain.schemas import PageText

OCR_DPI_SCALE = 2.5
MAX_EXTRACTED_CHARS = 80_000
OCR_TIMEOUT_SECONDS = 30
PDF_MAGIC = b"%PDF-"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class UnsupportedDocumentError(ValueError):
    pass


class DocumentLimitError(ValueError):
    pass


def detect_document_type(content: bytes, filename: str) -> str:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if content.startswith(PDF_MAGIC) and suffix == "pdf":
        return "application/pdf"
    if content.startswith(PNG_MAGIC) and suffix == "png":
        return "image/png"
    if content.startswith(b"\xff\xd8\xff") and suffix in {"jpg", "jpeg"}:
        return "image/jpeg"
    raise UnsupportedDocumentError(
        "The file extension and actual file signature must match PDF, PNG, or JPEG."
    )


def extract_pages(
    content: bytes,
    content_type: str,
    *,
    max_pages: int,
    max_image_pixels: int,
) -> list[PageText]:
    if content_type == "application/pdf":
        pages = _extract_pdf(content, max_pages=max_pages, max_image_pixels=max_image_pixels)
    elif content_type in {"image/png", "image/jpeg"}:
        pages = [_extract_image(content, max_image_pixels=max_image_pixels)]
    else:
        raise UnsupportedDocumentError("Only PDF, PNG, and JPEG documents are supported.")

    if sum(len(page.text) for page in pages) > MAX_EXTRACTED_CHARS:
        raise DocumentLimitError(
            f"Extracted text exceeds the {MAX_EXTRACTED_CHARS}-character model input "
            "limit; nothing was truncated."
        )
    return pages


def _extract_pdf(content: bytes, *, max_pages: int, max_image_pixels: int) -> list[PageText]:
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise UnsupportedDocumentError("Encrypted PDFs are not supported.")
        page_count = len(reader.pages)
    except UnsupportedDocumentError:
        raise
    except PdfReadError as exc:
        raise UnsupportedDocumentError("The PDF is malformed or could not be read.") from exc

    if not 1 <= page_count <= max_pages:
        raise DocumentLimitError(f"PDF must contain between 1 and {max_pages} pages.")

    pdfium_document = pdfium.PdfDocument(BytesIO(content))
    result: list[PageText] = []
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        method = "pdf-text"
        if len(text.strip()) < 20:
            rendered_page = pdfium_document[index]
            width, height = rendered_page.get_size()
            scale = min(OCR_DPI_SCALE, (max_image_pixels / max(width * height, 1)) ** 0.5)
            if width * scale * height * scale > max_image_pixels:
                raise DocumentLimitError(
                    "PDF page dimensions exceed the configured image-pixel limit."
                )
            image = rendered_page.render(scale=scale).to_pil()
            text = pytesseract.image_to_string(image, lang="por+eng", timeout=OCR_TIMEOUT_SECONDS)
            method = "tesseract"
        result.append(PageText(page=index + 1, text=text, method=method))
    return result


def _extract_image(content: bytes, *, max_image_pixels: int) -> PageText:
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            if image.width * image.height > max_image_pixels:
                raise DocumentLimitError(
                    "Image dimensions exceed the configured image-pixel limit."
                )
            text = pytesseract.image_to_string(
                image.convert("RGB"), lang="por+eng", timeout=OCR_TIMEOUT_SECONDS
            )
    except DocumentLimitError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedDocumentError("The image is corrupt or cannot be decoded.") from exc
    return PageText(page=1, text=text, method="tesseract")
