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
