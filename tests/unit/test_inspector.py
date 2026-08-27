import io

import fitz
import pytest

from app.config import Settings
from app.inspection.pdf_inspector import PdfInspector


def make_scanned_like_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 612, 792), 0)
    pix.clear_with(255)
    page.insert_image(page.rect, pixmap=pix)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def test_inspector_sets_fast_path_for_digital_pdf(tmp_path) -> None:
    document = fitz.open()
    page = document.new_page()
    paragraph = (
        "This is a dense digital paragraph used to validate the PyMuPDF fast-path inspection signal. "
        * 8
    )
    for line_index, chunk_start in enumerate(range(0, len(paragraph), 90)):
        page.insert_text((72, 72 + (line_index * 14)), paragraph[chunk_start : chunk_start + 90], fontsize=11)
    pdf_path = tmp_path / "digital.pdf"
    document.save(pdf_path)
    document.close()

    settings = Settings(
        extraction_output_dir=tmp_path / "output",
        extraction_database_path=tmp_path / "data" / "jobs.db",
    )
    inspector = PdfInspector(settings)
    inspection = inspector.inspect(pdf_path, document_id="doc")
    page_inspection = inspection.pages[0]
    assert page_inspection.probable_scan is False
    assert page_inspection.use_pymupdf_fast_path is True


def test_inspector_probable_scan_signal(tmp_path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(make_scanned_like_pdf_bytes())
    settings = Settings(
        extraction_output_dir=tmp_path / "output",
        extraction_database_path=tmp_path / "data" / "jobs.db",
    )
    inspector = PdfInspector(settings)
    inspection = inspector.inspect(pdf_path, document_id="scan")
    assert inspection.pages[0].probable_scan is True
