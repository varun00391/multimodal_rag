from __future__ import annotations

from app.models.common import bbox_from_seq
from app.models.region import Region


def assign_reading_order(regions: list[Region], page_width: float) -> list[Region]:
    if not regions:
        return regions
    mid = page_width / 2 if page_width else 0
    left_count = 0
    right_count = 0
    for region in regions:
        box = bbox_from_seq(region.bbox)
        if page_width and box.width < page_width * 0.55:
            if (box.x0 + box.x1) / 2 < mid:
                left_count += 1
            else:
                right_count += 1
    two_col = left_count >= 2 and right_count >= 2

    def sort_key(region: Region):
        box = bbox_from_seq(region.bbox)
        if two_col and page_width and box.width < page_width * 0.62:
            col = 0 if (box.x0 + box.x1) / 2 < mid else 1
        else:
            col = 0
        return (col, box.y0, box.x0)

    for order, region in enumerate(sorted(regions, key=sort_key), start=1):
        region.extra["reading_order"] = order
        if region.element:
            region.element.reading_order = order
    return regions
