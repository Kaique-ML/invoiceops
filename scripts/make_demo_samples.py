from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "demo"
LINES = [
    "SYNTHETIC DEMONSTRATION - NOT A TAX DOCUMENT",
    "Supplier: Cafe Aurora Comercio Ficticio Ltda.",
    "Tax ID: 00.000.000/0001-00",
    "Invoice number: DEMO-2026-001",
    "Issue date: 2026-06-15",
    "Currency: BRL",
    "Subtotal: 100.00",
    "Discounts: 0.00",
    "Taxes: 0.00",
    "Shipping: 0.00",
    "Tax included: yes",
    "Line item: Coffee beans | Quantity: 1 | Line total: 100.00",
    "Total: 100.00",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def create_samples() -> list[Path]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pdf_path = OUTPUT / "synthetic_invoice.pdf"
    canvas = Canvas(str(pdf_path), pagesize=A4)
    canvas.setFont("Helvetica", 12)
    _, page_height = A4
    for index, line in enumerate(LINES):
        canvas.drawString(48, page_height - 54 - index * 26, line)
    canvas.save()

    image = Image.new("RGB", (1700, 2100), "white")
    draw = ImageDraw.Draw(image)
    font = _font(43)
    for index, line in enumerate(LINES):
        draw.text((90, 100 + index * 135), line, fill="black", font=font)
    png_path = OUTPUT / "synthetic_invoice.png"
    jpg_path = OUTPUT / "synthetic_invoice.jpg"
    image.save(png_path, format="PNG", optimize=True)
    image.save(jpg_path, format="JPEG", quality=95, optimize=True)
    scan_path = OUTPUT / "synthetic_scanned_invoice.pdf"
    scan = Canvas(str(scan_path), pagesize=A4)
    scan.drawImage(
        ImageReader(str(png_path)),
        35,
        55,
        width=A4[0] - 70,
        height=A4[1] - 110,
        preserveAspectRatio=True,
        anchor="c",
    )
    scan.save()
    return [pdf_path, scan_path, png_path, jpg_path]


if __name__ == "__main__":
    for sample in create_samples():
        print(f"Created synthetic demo sample: {sample.relative_to(ROOT)}")
