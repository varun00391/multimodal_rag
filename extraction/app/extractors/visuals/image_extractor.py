from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.ingestion.storage import DocumentPaths
from app.models.figure import FigureModel
from app.profiling.pdf_profiler import open_pdf
from app.rendering.crop_renderer import crop_page_image


def extract_embedded_image(
    pdf_path: Path,
    xref: int,
    dest: Path,
) -> Path | None:
    doc = open_pdf(pdf_path)
    try:
        info = doc.extract_image(xref)
        if not info or not info.get("image"):
            return None
        ext = info.get("ext") or "png"
        dest = dest.with_suffix(f".{ext}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(info["image"])
        return dest
    except Exception:
        return None
    finally:
        doc.close()


def extract_image_region(
    *,
    pdf_path: Path,
    paths: DocumentPaths,
    page_image: Path,
    page_number: int,
    region_id: str,
    bbox_px: list[float],
    xref: int | None,
) -> FigureModel:
    settings = get_settings()
    original_asset = None
    if xref:
        dest = paths.images / f"{region_id}_original"
        saved = extract_embedded_image(pdf_path, xref, dest)
        if saved:
            original_asset = str(saved.relative_to(paths.root))
    crop_path = paths.images / f"{region_id}_crop.{settings.render_image_format}"
    crop_page_image(page_image, bbox_px, crop_path)
    return FigureModel(
        id=region_id,
        page=page_number,
        bbox=bbox_px,
        image_type="image",
        original_asset=original_asset,
        crop_asset=str(crop_path.relative_to(paths.root)),
    )
