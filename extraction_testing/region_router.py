"""Standalone region router (blueprint Step 7).

OCR and VLM are always in the plan. They are still invoked only by the
escalation rules in later steps (native text first, then OCR, then VLM).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pdf_profiler import PageProfile
from region_detector import Region

TEXT_TYPES = {
    "heading",
    "paragraph",
    "list",
    "footnote",
    "header",
    "footer",
    "caption",
}


def route_region(
    region: Region,
    page_profile: PageProfile | None = None,
) -> list[str]:
    scanned = bool(page_profile and page_profile.is_probably_scanned)
    region_type = region.type

    if region_type in TEXT_TYPES:
        return ["native_text", "ocr" if scanned else "ocr_fallback", "vlm"]

    if region_type in {"table", "complex_table"}:
        return ["table_engine", "ocr", "vlm_verify"]

    if region_type == "image":
        return ["image_extractor", "ocr", "vlm"]

    if region_type == "figure":
        return ["image_extractor", "ocr", "vlm"]

    if region_type == "chart":
        return ["image_extractor", "ocr", "vlm"]

    if region_type == "diagram":
        return ["pdf_vectors", "image_extractor", "ocr", "vlm"]

    if region_type in {"form", "signature", "screenshot", "scanned_document"}:
        return ["ocr", "layout", "vlm"]

    return ["native_text", "ocr_fallback", "vlm"]


def route_regions(
    regions: list[Region],
    page_profile: PageProfile | None = None,
) -> list[Region]:
    for region in regions:
        region.engines = route_region(region, page_profile)
    return regions


def count_routes(regions: list[Region]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for region in regions:
        for engine in region.engines:
            counts[engine] += 1
    return dict(counts)


def routing_plan(regions: list[Region]) -> list[dict[str, Any]]:
    return [
        {
            "region_id": region.id,
            "page": region.page,
            "type": region.type,
            "engines": list(region.engines),
        }
        for region in regions
    ]
