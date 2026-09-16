"""Standalone page renderer (blueprint Step 3 — RENDER, not EXTRACT).

Paints each PDF page to a PNG with PyMuPDF so later steps (OCR, layout,
crops, VLM, review) have pixels as well as native PDF objects.

Usage is through main.py; this module is the render step only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz

from pdf_profiler import open_pdf

# Frozen render config — keep this stable so pixel bboxes stay aligned.
DEFAULT_DPI = 200
IMAGE_FORMAT = "png"


@dataclass
class PageRender:
    page: int
    width_px: int
    height_px: int
    dpi: int
    path: str
    relative_path: str


def render_pages(
    pdf_path: str | Path,
    pages_dir: str | Path,
    dpi: int = DEFAULT_DPI,
    image_format: str = IMAGE_FORMAT,
) -> list[PageRender]:
    """Render every page to ``pages_dir/page_001.png`` (and so on)."""
    source = Path(pdf_path).expanduser().resolve()
    dest = Path(pages_dir)
    dest.mkdir(parents=True, exist_ok=True)

    if dpi <= 0:
        raise ValueError(f"dpi must be positive, got {dpi}")

    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)
    results: list[PageRender] = []

    doc = open_pdf(source)
    try:
        if doc.page_count < 1:
            raise RuntimeError("PDF has no pages.")
        for index in range(doc.page_count):
            page = doc.load_page(index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            filename = f"page_{index + 1:03d}.{image_format.lower()}"
            out_path = dest / filename
            pix.save(str(out_path))
            results.append(
                PageRender(
                    page=index + 1,
                    width_px=int(pix.width),
                    height_px=int(pix.height),
                    dpi=dpi,
                    path=str(out_path.resolve()),
                    relative_path=f"pages/{filename}",
                )
            )
    finally:
        doc.close()
    return results


def renders_to_dict(renders: list[PageRender]) -> list[dict[str, Any]]:
    return [asdict(item) for item in renders]
