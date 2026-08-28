from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.models.canonical import BoundingBox

from app.adapters.gemini_schema import GeminiBBox


@dataclass(frozen=True)
class RenderedPage:
    page: int
    width: float
    height: float
    rotation: int
    png_bytes: bytes
    mime_type: str = "image/png"


def consecutive_groups(pages: list[int], *, target: int, max_size: int) -> list[list[int]]:
    if not pages:
        return []
    ordered = sorted(set(pages))
    chunk_size = max(1, min(target, max_size))
    runs: list[list[int]] = [[ordered[0]]]
    for page in ordered[1:]:
        if page == runs[-1][-1] + 1:
            runs[-1].append(page)
        else:
            runs.append([page])

    groups: list[list[int]] = []
    for run in runs:
        for start in range(0, len(run), chunk_size):
            groups.append(run[start : start + chunk_size])
    return groups


def render_scale(width: float, height: float, max_pixels: int, *, preferred: float = 1.5) -> float:
    area = max(1.0, width * height)
    scale = preferred
    if area * scale * scale > max_pixels:
        scale = math.sqrt(max_pixels / area)
    return max(0.25, scale)


def persist_rendered_pages(pdf_path: Path, rendered: list[RenderedPage]) -> list[str]:
    assets_dir = pdf_path.parent / "assets" / "pages"
    assets_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for item in rendered:
        relative = f"assets/pages/page_{item.page}.png"
        (pdf_path.parent / relative).write_bytes(item.png_bytes)
        saved.append(relative)
    return saved


def render_pages(
    pdf_path: Path,
    pages: list[int],
    *,
    max_pixels: int,
) -> list[RenderedPage]:
    document = fitz.open(pdf_path)
    rendered: list[RenderedPage] = []
    try:
        for page_number in pages:
            page = document.load_page(page_number - 1)
            width = page.rect.width
            height = page.rect.height
            scale = render_scale(width, height, max_pixels)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            rendered.append(
                RenderedPage(
                    page=page_number,
                    width=width,
                    height=height,
                    rotation=page.rotation,
                    png_bytes=pix.tobytes("png"),
                )
            )
    finally:
        document.close()
    return rendered


def bbox_to_pdf_points(
    bbox: GeminiBBox,
    page_width: float,
    page_height: float,
) -> BoundingBox:
    left, top, right, bottom = bbox.left, bbox.top, bbox.right, bbox.bottom
    max_value = max(abs(left), abs(top), abs(right), abs(bottom), 0.0)
    if max_value > 1.5:
        page_max = max(page_width, page_height)
        divisor = 1000.0 if max_value <= 1000.5 or max_value > page_max * 1.2 else 1.0
        if divisor != 1.0:
            left, top, right, bottom = (
                left / divisor,
                top / divisor,
                right / divisor,
                bottom / divisor,
            )
            max_value = max(abs(left), abs(top), abs(right), abs(bottom), 0.0)
        if max_value > 1.5:
            return _clamp_bbox(
                BoundingBox(left=left, top=top, right=right, bottom=bottom),
                page_width,
                page_height,
            )
    return _clamp_bbox(
        BoundingBox(
            left=left * page_width,
            top=top * page_height,
            right=right * page_width,
            bottom=bottom * page_height,
        ),
        page_width,
        page_height,
    )


def _clamp_bbox(bbox: BoundingBox, page_width: float, page_height: float) -> BoundingBox:
    left = min(bbox.left, bbox.right)
    right = max(bbox.left, bbox.right)
    top = min(bbox.top, bbox.bottom)
    bottom = max(bbox.top, bbox.bottom)
    return BoundingBox(
        left=max(0.0, min(left, page_width)),
        top=max(0.0, min(top, page_height)),
        right=max(0.0, min(right, page_width)),
        bottom=max(0.0, min(bottom, page_height)),
    )
