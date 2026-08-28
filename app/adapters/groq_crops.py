from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from app.merge.coordinates import rect_to_bbox
from app.models.canonical import BoundingBox


@dataclass(frozen=True)
class VisualCrop:
    page: int
    bbox: BoundingBox
    png_bytes: bytes
    asset: str
    nearby_text: str = ""
    caption: str = ""


def crop_region(
    pdf_path: Path,
    page_number: int,
    region: list[float],
    *,
    index: int = 1,
    max_pixels: int = 4_000_000,
) -> VisualCrop:
    document = fitz.open(pdf_path)
    try:
        page = document.load_page(page_number - 1)
        left, top, right, bottom = [float(value) for value in region]
        clip = fitz.Rect(left, top, right, bottom) & page.rect
        if clip.is_empty or clip.width < 2 or clip.height < 2:
            raise ValueError(f"Visual region on page {page_number} is empty or too small.")
        scale = min(2.0, (max_pixels / max(clip.width * clip.height, 1.0)) ** 0.5)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
        nearby, caption = _nearby_text(page, clip)
        asset = _persist_crop(pdf_path, page_number, index, pix.tobytes("png"))
        return VisualCrop(
            page=page_number,
            bbox=rect_to_bbox((clip.x0, clip.y0, clip.x1, clip.y1)),
            png_bytes=pix.tobytes("png"),
            asset=asset,
            nearby_text=nearby,
            caption=caption,
        )
    finally:
        document.close()


def _persist_crop(pdf_path: Path, page_number: int, index: int, png_bytes: bytes) -> str:
    relative = f"assets/charts/page_{page_number}_r{index}.png"
    destination = pdf_path.parent / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(png_bytes)
    return relative


def _nearby_text(page: fitz.Page, clip: fitz.Rect) -> tuple[str, str]:
    page_dict = page.get_text("dict")
    nearby: list[str] = []
    captions: list[str] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox = fitz.Rect(block.get("bbox", (0, 0, 0, 0)))
        text = _block_text(block)
        if not text:
            continue
        expanded = fitz.Rect(clip.x0 - 12, clip.y0 - 12, clip.x1 + 12, clip.y1 + 48)
        if bbox.intersects(expanded):
            nearby.append(text)
        below = bbox.y0 >= clip.y1 - 8 and bbox.y0 <= clip.y1 + 36 and bbox.x0 < clip.x1 and bbox.x1 > clip.x0
        if below and len(text) < 240:
            captions.append(text)
    return " ".join(nearby)[:500], " ".join(captions)[:240]


def _block_text(block: dict) -> str:
    parts: list[str] = []
    for line in block.get("lines", []):
        line_text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
        if line_text:
            parts.append(line_text)
    return " ".join(parts)
