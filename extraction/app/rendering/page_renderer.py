from __future__ import annotations

from pathlib import Path

import fitz

from app.core.config import get_settings
from app.ingestion.storage import DocumentPaths
from app.profiling.pdf_profiler import open_pdf


def render_pages(pdf_path: Path, paths: DocumentPaths, dpi: int | None = None) -> list[dict]:
    settings = get_settings()
    dpi = dpi or settings.render_dpi
    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)
    image_format = settings.render_image_format.lower()
    results: list[dict] = []
    doc = open_pdf(pdf_path)
    try:
        for index in range(doc.page_count):
            page = doc.load_page(index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            filename = f"page_{index + 1:03d}.{image_format}"
            out_path = paths.pages / filename
            pix.save(str(out_path))
            results.append(
                {
                    "page": index + 1,
                    "width_px": pix.width,
                    "height_px": pix.height,
                    "dpi": dpi,
                    "path": str(out_path),
                    "relative_path": f"artifacts/pages/{filename}",
                }
            )
    finally:
        doc.close()
    return results
