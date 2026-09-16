"""Standalone region tree (blueprint Step 6).

Step 5 produces a flat list of typed regions. This step adds parent/child
links so a figure can own its chart and caption, or a table can own a
footnote. It does not extract cell/chart content — it only nests regions.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from region_detector import Region, region_to_dict

CONTAINER_TYPES = {
    "figure",
    "chart",
    "diagram",
    "table",
    "complex_table",
    "image",
}
NESTABLE_TYPES = {
    "caption",
    "footnote",
    "table",
    "complex_table",
    "chart",
    "diagram",
    "image",
    "figure",
    "heading",
    "list",
}
VISUAL_TYPES = {"image", "figure", "chart", "diagram", "table", "complex_table"}
CONTAINMENT_RATIO = 0.8
MIN_PARENT_AREA_RATIO = 1.05
CAPTION_MAX_DISTANCE_PX = 100.0
FOOTNOTE_MAX_DISTANCE_PX = 80.0


def build_region_tree(regions: list[Region]) -> list[Region]:
    """Attach parent_id / children on the existing region objects."""
    if not regions:
        return regions
    _reset_tree(regions)
    _nest_contained_regions(regions)
    _attach_captions(regions)
    _attach_footnotes(regions)
    _promote_images_to_figures(regions)
    return regions


def tree_stats(regions: list[Region]) -> dict[str, Any]:
    roots = [region for region in regions if not region.parent_id]
    nested = [region for region in regions if region.parent_id]
    by_id = {region.id: region for region in regions}
    relations: Counter[str] = Counter()
    for child in nested:
        parent = by_id.get(child.parent_id or "")
        if parent is None:
            continue
        relations[f"{child.type}->{parent.type}"] += 1
    return {
        "region_count": len(regions),
        "root_count": len(roots),
        "nested_count": len(nested),
        "relations": dict(relations),
    }


def regions_as_nested_tree(regions: list[Region]) -> list[dict[str, Any]]:
    by_id = {region.id: region for region in regions}
    roots = [region for region in regions if not region.parent_id]

    def node(region: Region) -> dict[str, Any]:
        payload = region_to_dict(region)
        payload["children_nodes"] = [
            node(by_id[child_id]) for child_id in region.children if child_id in by_id
        ]
        return payload

    return [node(region) for region in roots]


def _reset_tree(regions: list[Region]) -> None:
    for region in regions:
        region.parent_id = None
        region.children = []


def _nest_contained_regions(regions: list[Region]) -> None:
    by_id = {region.id: region for region in regions}
    candidates = sorted(regions, key=lambda region: _area(region.bbox), reverse=True)
    for child in sorted(regions, key=lambda region: _area(region.bbox)):
        if child.type not in NESTABLE_TYPES:
            continue
        parent = _smallest_container(child, candidates)
        if parent is None:
            continue
        _attach(parent, child, by_id)


def _smallest_container(child: Region, candidates: list[Region]) -> Region | None:
    child_area = _area(child.bbox)
    if child_area <= 0:
        return None
    best: Region | None = None
    best_area = float("inf")
    for parent in candidates:
        if parent.id == child.id or parent.page != child.page:
            continue
        if parent.type not in CONTAINER_TYPES:
            continue
        parent_area = _area(parent.bbox)
        if parent_area < child_area * MIN_PARENT_AREA_RATIO:
            continue
        if _containment_ratio(child.bbox, parent.bbox) < CONTAINMENT_RATIO:
            continue
        if parent_area < best_area:
            best = parent
            best_area = parent_area
    return best


def _attach_captions(regions: list[Region]) -> None:
    by_id = {region.id: region for region in regions}
    captions = [region for region in regions if region.type == "caption" and not region.parent_id]
    visuals = [region for region in regions if region.type in VISUAL_TYPES]
    for caption in captions:
        owner = _nearest_visual(caption, visuals)
        if owner is None:
            continue
        _attach(owner, caption, by_id)


def _attach_footnotes(regions: list[Region]) -> None:
    by_id = {region.id: region for region in regions}
    footnotes = [region for region in regions if region.type == "footnote" and not region.parent_id]
    tables = [region for region in regions if region.type in {"table", "complex_table"}]
    for footnote in footnotes:
        owner = _nearest_below(footnote, tables, FOOTNOTE_MAX_DISTANCE_PX)
        if owner is None:
            continue
        _attach(owner, footnote, by_id)


def _promote_images_to_figures(regions: list[Region]) -> None:
    by_id = {region.id: region for region in regions}
    for region in regions:
        if region.type != "image":
            continue
        child_types = {
            by_id[child_id].type for child_id in region.children if child_id in by_id
        }
        if "caption" in child_types:
            region.type = "figure"


def _nearest_visual(caption: Region, visuals: list[Region]) -> Region | None:
    preferred = [visual for visual in visuals if _caption_matches(caption, visual)]
    pool = preferred or visuals
    return _nearest_below(caption, pool, CAPTION_MAX_DISTANCE_PX)


def _caption_matches(caption: Region, visual: Region) -> bool:
    text = str((caption.extra or {}).get("text") or "").strip().lower()
    if text.startswith("table"):
        return visual.type in {"table", "complex_table"}
    if text.startswith(("figure", "fig.")):
        return visual.type in {"figure", "image", "diagram", "chart"}
    if text.startswith("chart"):
        return visual.type in {"chart", "diagram", "figure", "image"}
    return True


def _nearest_below(source: Region, candidates: list[Region], max_distance: float) -> Region | None:
    src = _as_box(source.bbox)
    src_c = _center(src)
    best: Region | None = None
    best_dist = max_distance
    for candidate in candidates:
        if candidate.page != source.page or candidate.id == source.id:
            continue
        box = _as_box(candidate.bbox)
        cand_c = _center(box)
        if src[1] >= box[3] - 16:
            dist = abs(src[1] - box[3])
        else:
            dist = ((src_c[0] - cand_c[0]) ** 2 + (src_c[1] - cand_c[1]) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best = candidate
    return best


def _attach(parent: Region, child: Region, by_id: dict[str, Region]) -> None:
    if child.parent_id or parent.id == child.id:
        return
    if _is_descendant(child, parent, by_id):
        return
    child.parent_id = parent.id
    if child.id not in parent.children:
        parent.children.append(child.id)


def _is_descendant(ancestor: Region, node: Region, by_id: dict[str, Region]) -> bool:
    current = node
    seen: set[str] = set()
    while current.parent_id:
        if current.parent_id in seen:
            return True
        seen.add(current.parent_id)
        if current.parent_id == ancestor.id:
            return True
        nxt = by_id.get(current.parent_id)
        if nxt is None:
            return False
        current = nxt
    return False


def _containment_ratio(child_bbox: list[float], parent_bbox: list[float]) -> float:
    child = _as_box(child_bbox)
    parent = _as_box(parent_bbox)
    area = _box_area(child)
    if area <= 0:
        return 0.0
    return _intersection_area(child, parent) / area


def _area(bbox: list[float]) -> float:
    if not bbox or len(bbox) < 4:
        return 0.0
    return _box_area(_as_box(bbox))


def _as_box(seq: list[float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _box_area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
