from __future__ import annotations

from app.core.config import get_settings
from app.models.document import DocumentProfile
from app.models.page import PageProfile
from app.models.region import Region


def plan_page(page_profile: PageProfile, regions: list[Region]) -> dict:
    settings = get_settings()
    use_ocr = settings.ocr_enabled and (
        page_profile.is_probably_scanned or page_profile.native_text_chars < settings.min_native_text_chars
    )
    use_vlm = settings.vlm_enabled and any(
        region.type.value in {"chart", "diagram", "form", "complex_table"} for region in regions
    )
    return {
        "use_ocr": use_ocr,
        "use_vlm": use_vlm,
        "table_engine": settings.table_engine,
        "ocr_engine": settings.ocr_engine,
    }


def plan_document(profile: DocumentProfile) -> dict:
    settings = get_settings()
    return {
        "document_kind": (
            "scanned"
            if profile.is_probably_scanned
            else "hybrid"
            if profile.is_hybrid
            else "born_digital"
        ),
        "ocr_enabled": settings.ocr_enabled,
        "vlm_enabled": settings.vlm_enabled,
        "table_engine": settings.table_engine,
    }
