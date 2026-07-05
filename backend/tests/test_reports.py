from io import BytesIO

from PIL import Image

from app.analysis import analyze_image_bytes
from app.reports import build_pdf_report


def test_pdf_report_is_generated() -> None:
    image = Image.new("RGB", (48, 48), "white")
    output = BytesIO()
    image.save(output, format="PNG")

    result = analyze_image_bytes(output.getvalue())
    pdf = build_pdf_report(result)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
