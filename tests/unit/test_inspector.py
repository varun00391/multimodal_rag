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


def test_inspector_detects_mid_page_figure_not_full_page_scan(tmp_path) -> None:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    paragraph = (
        "This dense digital paragraph keeps the page from being classified as a scan. "
        * 8
    )
    for line_index, chunk_start in enumerate(range(0, len(paragraph), 90)):
        page.insert_text((72, 36 + (line_index * 12)), paragraph[chunk_start : chunk_start + 90], fontsize=10)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 120), 0)
    pix.clear_with(160)
    page.insert_image(fitz.Rect(100, 220, 500, 460), pixmap=pix)
    page.insert_text((100, 480), "Figure 1. Revenue by region.", fontsize=10)
    pdf_path = tmp_path / "figure.pdf"
    document.save(pdf_path)
    document.close()

    settings = Settings(
        extraction_output_dir=tmp_path / "output",
        extraction_database_path=tmp_path / "data" / "jobs.db",
    )
    inspection = PdfInspector(settings).inspect(pdf_path, document_id="figure")
    page_inspection = inspection.pages[0]
    assert page_inspection.probable_scan is False
    assert page_inspection.figure_regions
    left, top, right, bottom = page_inspection.figure_regions[0]
    coverage = ((right - left) * (bottom - top)) / (page_inspection.width * page_inspection.height)
    assert 0.08 <= coverage < 0.75


def test_inspector_skips_full_page_scan_and_tiny_logo(tmp_path) -> None:
    scan_path = tmp_path / "scan.pdf"
    scan_path.write_bytes(make_scanned_like_pdf_bytes())
    settings = Settings(
        extraction_output_dir=tmp_path / "output",
        extraction_database_path=tmp_path / "data" / "jobs.db",
    )
    scan = PdfInspector(settings).inspect(scan_path, document_id="scan")
    assert scan.pages[0].probable_scan is True
    assert scan.pages[0].figure_regions == []

    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 72), "Logo only page with plenty of native text. " * 20)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 24, 24), 0)
    pix.clear_with(40)
    page.insert_image(fitz.Rect(20, 20, 44, 44), pixmap=pix)
    logo_path = tmp_path / "logo.pdf"
    document.save(logo_path)
    document.close()
    logo = PdfInspector(settings).inspect(logo_path, document_id="logo")
    assert logo.pages[0].figure_regions == []
