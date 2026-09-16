"""VLM extraction for visual regions (charts, diagrams, figures, images)."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from image_utils import crop_region
from region_detector import Region
from vlm_client import VLMError, get_vlm_client, prompt_for_region_type

VISUAL_TYPES = {"chart", "diagram", "figure", "image"}


@dataclass
class VisualExtraction:
    region_id: str
    page: int
    type: str
    source: str
    status: str
    crop_path: str | None = None
    content: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def extract_visual_regions(
    regions: list[Region],
    page_image: str | Path | None,
    crops_dir: str | Path,
) -> list[VisualExtraction]:
    results: list[VisualExtraction] = []
    for region in regions:
        if region.type not in VISUAL_TYPES:
            continue
        if "vlm" not in region.engines:
            continue
        results.append(_extract_one(region, page_image, Path(crops_dir)))
    return results


def visual_to_dict(item: VisualExtraction) -> dict[str, Any]:
    return asdict(item)


def count_visual_status(items: list[VisualExtraction]) -> dict[str, int]:
    return dict(Counter(item.status for item in items))


def _extract_one(
    region: Region,
    page_image: str | Path | None,
    crops_dir: Path,
) -> VisualExtraction:
    notes: list[str] = []
    if page_image is None:
        return VisualExtraction(
            region_id=region.id,
            page=region.page,
            type=region.type,
            source="vlm",
            status="failed",
            notes=["no page image for VLM crop"],
        )
    crop_path = crops_dir / f"{region.id}.png"
    try:
        crop_region(page_image, region.bbox, crop_path)
    except Exception as exc:
        return VisualExtraction(
            region_id=region.id,
            page=region.page,
            type=region.type,
            source="vlm",
            status="failed",
            notes=[f"crop failed: {exc}"],
        )
    try:
        content = get_vlm_client().analyze_image(
            crop_path, prompt_for_region_type(region.type)
        )
        notes.append(f"euron:{content.get('_model')}")
        return VisualExtraction(
            region_id=region.id,
            page=region.page,
            type=region.type,
            source="vlm",
            status="accepted_vlm",
            crop_path=str(crop_path),
            content=content,
            notes=notes,
        )
    except VLMError as exc:
        return VisualExtraction(
            region_id=region.id,
            page=region.page,
            type=region.type,
            source="vlm",
            status="failed",
            crop_path=str(crop_path),
            notes=[str(exc)],
        )
