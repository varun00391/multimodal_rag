from __future__ import annotations

import fitz

from app.core.config import get_settings
from app.models.page import PageProfile


def profile_page(page: fitz.Page, page_number: int) -> PageProfile:
    settings = get_settings()
    rect = page.rect
    text = page.get_text("text") or ""
    native_text_chars = len(text.strip())
    images = page.get_images(full=True) or []
    drawings = page.get_drawings() or []
    annots = list(page.annots() or [])
    links = page.get_links() or []
    fonts = page.get_fonts() or []
    area = max(1.0, rect.width * rect.height)
    density = native_text_chars / (area / (72.0 * 72.0))
    large_image_cover = _image_cover_ratio(page, images)
    is_probably_scanned = native_text_chars < settings.min_native_text_chars or (
        density < settings.scanned_text_density_threshold
        and large_image_cover > 0.6
        and native_text_chars < 400
    )
    has_ocr_layer = bool(native_text_chars > 0 and large_image_cover > 0.7)
    dpi = settings.render_dpi
    scale = dpi / 72.0
    return PageProfile(
        page_number=page_number,
        width=float(rect.width),
        height=float(rect.height),
        width_px=int(round(rect.width * scale)),
        height_px=int(round(rect.height * scale)),
        rotation=int(page.rotation or 0),
        native_text_chars=native_text_chars,
        image_count=len(images),
        vector_count=len(drawings),
        has_ocr_layer=has_ocr_layer,
        is_probably_scanned=bool(is_probably_scanned),
        font_count=len(fonts),
        annotation_count=len(annots),
        link_count=len(links),
        mediabox=[float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
    )


def _image_cover_ratio(page: fitz.Page, images: list) -> float:
    if not images:
        return 0.0
    page_area = max(1.0, page.rect.width * page.rect.height)
    covered = 0.0
    for image in images:
        xref = image[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            continue
        for rect in rects:
            covered += max(0.0, rect.width * rect.height)
    return min(1.0, covered / page_area)
