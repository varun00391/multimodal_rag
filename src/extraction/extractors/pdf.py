from __future__ import annotations

from pathlib import Path

import pymupdf

from extraction.elements import picture_element, table_element, text_element
from extraction.errors import ExtractionError
from extraction.extractors.ocr import ocr_image
from extraction.models.cdr import BBox, Diagnostic, Unit
from extraction.models.report import ExtractionReport, RouteRecord
from extraction.settings import Settings

VERSION = "1.0"


def _bbox(rect: pymupdf.Rect | tuple | list) -> BBox:
    if hasattr(rect, "x0"):
        return BBox(left=rect.x0, top=rect.y0, right=rect.x1, bottom=rect.y1)
    left, top, right, bottom = rect[:4]
    return BBox(left=left, top=top, right=right, bottom=bottom)


def _save_pixmap(pix: pymupdf.Pixmap, dest: Path) -> None:
    if pix.n - pix.alpha > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pix.save(dest)


def _extract_native_page(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    page_index: int,
    assets_dir: Path,
) -> Unit:
    elements = []
    order = 1
    blocks = page.get_text("dict").get("blocks", [])
    text_blocks = [block for block in blocks if block.get("type") == 0]
    text_blocks.sort(key=lambda block: (round(block.get("bbox", [0, 0, 0, 0])[1], 1), block.get("bbox", [0])[0]))
    for block in text_blocks:
        lines = []
        for line in block.get("lines", []):
            line_text = " ".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if line_text:
                lines.append(line_text)
        text = "\n".join(lines).strip()
        if not text:
            continue
        bbox = block.get("bbox")
        elements.append(
            text_element(
                unit_type="page",
                unit_index=page_index,
                order=order,
                text=text,
                extractor="pymupdf",
                version=VERSION,
                bbox=BBox(left=bbox[0], top=bbox[1], right=bbox[2], bottom=bbox[3]) if bbox else None,
            )
        )
        order += 1
    try:
        finder = page.find_tables()
        tables = finder.tables if finder is not None else []
    except Exception:
        tables = []
    for table in tables:
        raw = table.extract()
        if not raw:
            continue
        columns = [str(cell or "").strip() for cell in raw[0]]
        rows = [[str(cell or "").strip() for cell in row] for row in raw[1:]]
        elements.append(
            table_element(
                unit_type="page",
                unit_index=page_index,
                order=order,
                columns=columns,
                rows=rows,
                extractor="pymupdf",
                version=VERSION,
                bbox=_bbox(table.bbox) if getattr(table, "bbox", None) else None,
            )
        )
        order += 1
    for image_index, image in enumerate(page.get_images(full=True), start=1):
        xref = image[0]
        dest = assets_dir / f"page-{page_index}-image-{image_index}.png"
        try:
            pix = pymupdf.Pixmap(doc, xref)
            _save_pixmap(pix, dest)
        except Exception:
            continue
        elements.append(
            picture_element(
                unit_type="page",
                unit_index=page_index,
                order=order,
                asset_path=str(dest.name),
                extractor="pymupdf",
                version=VERSION,
            )
        )
        order += 1
    return Unit(
        unit_type="page",
        index=page_index,
        primary_route="pymupdf",
        width=page.rect.width,
        height=page.rect.height,
        elements=elements,
        error=None if elements else "NATIVE_TEXT_EMPTY",
    )


def _extract_ocr_page(
    page: pymupdf.Page,
    page_index: int,
    assets_dir: Path,
    diagnostics: list[Diagnostic],
) -> Unit:
    render = assets_dir / f"page-{page_index}-raster.png"
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    _save_pixmap(pix, render)
    try:
        text, confidence = ocr_image(render)
    except ExtractionError as exc:
        diagnostics.append(Diagnostic(code=exc.code, message=exc.message, unit_index=page_index))
        return Unit(
            unit_type="page",
            index=page_index,
            primary_route="paddleocr",
            width=page.rect.width,
            height=page.rect.height,
            error=exc.code,
        )
    elements = []
    if text:
        elements.append(
            text_element(
                unit_type="page",
                unit_index=page_index,
                order=1,
                text=text,
                extractor="paddleocr",
                version=VERSION,
                confidence=confidence,
            )
        )
    return Unit(
        unit_type="page",
        index=page_index,
        primary_route="paddleocr",
        width=page.rect.width,
        height=page.rect.height,
        elements=elements,
        error=None if elements else "OCR_EMPTY",
    )


def extract_pdf(
    settings: Settings,
    path: Path,
    assets_dir: Path,
    page_routes: list[str],
    report: ExtractionReport,
    diagnostics: list[Diagnostic],
) -> list[Unit]:
    del settings
    units: list[Unit] = []
    with pymupdf.open(path) as doc:
        for page_index, page in enumerate(doc, start=1):
            route = page_routes[page_index - 1] if page_index - 1 < len(page_routes) else "pymupdf"
            report.routes.append(RouteRecord(unit_type="page", index=page_index, extractor=route))
            if route == "paddleocr":
                units.append(_extract_ocr_page(page, page_index, assets_dir, diagnostics))
            else:
                units.append(_extract_native_page(doc, page, page_index, assets_dir))
    return units
