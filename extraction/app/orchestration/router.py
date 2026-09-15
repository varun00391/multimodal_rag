from __future__ import annotations

from app.core.config import get_settings
from app.models.common import RegionType
from app.models.page import PageProfile
from app.models.region import Region


def route_region(region: Region, page_profile: PageProfile | None = None) -> list[str]:
    settings = get_settings()
    scanned = bool(page_profile and page_profile.is_probably_scanned)
    region_type = region.type

    if region_type in {
        RegionType.HEADING,
        RegionType.PARAGRAPH,
        RegionType.LIST,
        RegionType.FOOTNOTE,
        RegionType.HEADER,
        RegionType.FOOTER,
        RegionType.CAPTION,
    }:
        engines = ["native_text"]
        if settings.ocr_enabled and scanned:
            engines.append("ocr")
        elif settings.ocr_enabled:
            engines.append("ocr_fallback")
        return engines

    if region_type in {RegionType.TABLE, RegionType.COMPLEX_TABLE}:
        engines = ["table_engine"]
        if settings.ocr_enabled:
            engines.append("ocr")
        if settings.vlm_enabled and region_type == RegionType.COMPLEX_TABLE:
            engines.append("vlm_verify")
        return engines

    if region_type == RegionType.IMAGE:
        return ["image_extractor"]

    if region_type == RegionType.FIGURE:
        engines = ["image_extractor"]
        if settings.ocr_enabled:
            engines.append("ocr")
        return engines

    if region_type == RegionType.CHART:
        engines = ["image_extractor"]
        if settings.ocr_enabled:
            engines.append("ocr")
        if settings.vlm_enabled:
            engines.append("vlm")
        return engines

    if region_type == RegionType.DIAGRAM:
        engines = ["pdf_vectors", "image_extractor"]
        if settings.ocr_enabled:
            engines.append("ocr")
        if settings.vlm_enabled:
            engines.append("vlm")
        return engines

    if region_type in {RegionType.FORM, RegionType.SIGNATURE}:
        engines = ["image_extractor"]
        if settings.ocr_enabled:
            engines.append("ocr")
        if settings.vlm_enabled:
            engines.append("vlm")
        return engines

    if settings.vlm_enabled:
        return ["vlm"]
    return ["native_text", "ocr_fallback"] if settings.ocr_enabled else ["native_text"]
