from app.models.canonical import BoundingBox


def rect_to_bbox(rect: tuple[float, float, float, float] | list[float]) -> BoundingBox:
    left, top, right, bottom = rect
    return BoundingBox(
        left=float(left),
        top=float(top),
        right=float(right),
        bottom=float(bottom),
    )


def sort_reading_order(items: list[tuple[int, BoundingBox]]) -> list[tuple[int, BoundingBox]]:
    return sorted(items, key=lambda item: (round(item[1].top, 1), item[1].left))


def normalize_origin(origin: str | None) -> str:
    return (origin or "top-left").strip().lower().replace("_", "-")


def bbox_iou(left: BoundingBox, right: BoundingBox) -> float:
    intersection = _intersection_area(left, right)
    if intersection <= 0:
        return 0.0
    union = left.area + right.area - intersection
    return intersection / union if union > 0 else 0.0


def containment_ratio(inner: BoundingBox, outer: BoundingBox) -> float:
    if inner.area <= 0:
        return 0.0
    return _intersection_area(inner, outer) / inner.area


def normalize_bbox(
    bbox: BoundingBox,
    page_width: float,
    page_height: float,
) -> BoundingBox:
    left, top, right, bottom = bbox.left, bbox.top, bbox.right, bbox.bottom
    origin = normalize_origin(bbox.coordinate_origin)
    if "bottom" in origin:
        top, bottom = page_height - bottom, page_height - top
    if left > right:
        left, right = right, left
    if top > bottom:
        top, bottom = bottom, top
    left = _clamp(left, 0.0, page_width)
    right = _clamp(right, 0.0, page_width)
    top = _clamp(top, 0.0, page_height)
    bottom = _clamp(bottom, 0.0, page_height)
    if right < left:
        right = left
    if bottom < top:
        bottom = top
    return BoundingBox(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        coordinate_origin="top-left",
        unit="pdf-point",
    )


def _intersection_area(left: BoundingBox, right: BoundingBox) -> float:
    x_overlap = min(left.right, right.right) - max(left.left, right.left)
    y_overlap = min(left.bottom, right.bottom) - max(left.top, right.top)
    if x_overlap <= 0 or y_overlap <= 0:
        return 0.0
    return x_overlap * y_overlap


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)
