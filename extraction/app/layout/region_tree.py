from __future__ import annotations

from app.models.common import RegionType, bbox_from_seq, center
from app.models.region import Region

CAPTION_MAX_DISTANCE = 80


def build_region_tree(regions: list[Region]) -> list[Region]:
    captions = [r for r in regions if r.type == RegionType.CAPTION]
    visuals = [
        r
        for r in regions
        if r.type
        in {
            RegionType.IMAGE,
            RegionType.FIGURE,
            RegionType.CHART,
            RegionType.DIAGRAM,
            RegionType.TABLE,
            RegionType.COMPLEX_TABLE,
        }
    ]
    for caption in captions:
        owner = _nearest(caption, visuals)
        if owner is None:
            continue
        caption.parent_id = owner.id
        if caption.id not in owner.children:
            owner.children.append(caption.id)
        if owner.type == RegionType.IMAGE:
            owner.type = RegionType.FIGURE
    return regions


def _nearest(caption: Region, candidates: list[Region]) -> Region | None:
    cap = bbox_from_seq(caption.bbox)
    cap_c = center(cap)
    best: Region | None = None
    best_dist = CAPTION_MAX_DISTANCE
    for candidate in candidates:
        if candidate.page != caption.page:
            continue
        box = bbox_from_seq(candidate.bbox)
        cand_c = center(box)
        vertical = abs(cap.y0 - box.y1)
        if cap.y0 >= box.y1 - 8:
            dist = vertical
        else:
            dist = ((cap_c[0] - cand_c[0]) ** 2 + (cap_c[1] - cand_c[1]) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best = candidate
    return best
