from __future__ import annotations

from collections import Counter

from app.inspection.features import overlap_ratio
from app.models.canonical import CanonicalElement, CanonicalPage, ElementType
from app.models.validation import ValidationFailure

BBOX_TOLERANCE = 1.0
MAX_OVERLAP_RATIO = 0.60
TEXT_TYPES = {ElementType.HEADING, ElementType.PARAGRAPH, ElementType.LIST}


def validate_layout(page: CanonicalPage) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    boxes: list[tuple[float, float, float, float]] = []

    for element in page.elements:
        bbox = element.bbox
        if bbox is None:
            continue
        if bbox.area <= 0:
            failures.append(
                ValidationFailure(
                    code="BBOX_NON_POSITIVE_AREA",
                    message="Element bounding box has no positive area.",
                    element_id=element.element_id,
                )
            )
            continue
        if not _inside_page(bbox.left, bbox.top, bbox.right, bbox.bottom, page.width, page.height):
            failures.append(
                ValidationFailure(
                    code="BBOX_OUT_OF_BOUNDS",
                    message="Element bounding box extends outside the page.",
                    element_id=element.element_id,
                    details={
                        "left": round(bbox.left, 2),
                        "top": round(bbox.top, 2),
                        "right": round(bbox.right, 2),
                        "bottom": round(bbox.bottom, 2),
                    },
                )
            )
        boxes.append((bbox.left, bbox.top, bbox.right, bbox.bottom))

    orders = [element.reading_order for element in page.elements]
    if orders and (len(set(orders)) != len(orders) or min(orders) < 1):
        failures.append(
            ValidationFailure(
                code="READING_ORDER_INVALID",
                message="Reading-order indices are missing, duplicated, or not 1-based.",
                details={"count": len(orders), "unique": len(set(orders))},
            )
        )
    elif _reading_order_inversions(page.elements) > 0.60:
        failures.append(
            ValidationFailure(
                code="READING_ORDER_INVALID",
                message="Reading order disagrees with top-to-bottom, left-to-right geometry.",
            )
        )

    if overlap_ratio(boxes) > MAX_OVERLAP_RATIO:
        failures.append(
            ValidationFailure(
                code="EXCESSIVE_OVERLAP",
                message="Too many extracted elements overlap on the page.",
                details={"overlap_ratio": round(overlap_ratio(boxes), 4)},
            )
        )

    texts = [
        (element.element_id, _normalize(element.text))
        for element in page.elements
        if element.type in TEXT_TYPES and element.text
    ]
    counts = Counter(text for _element_id, text in texts if text)
    for text, count in counts.items():
        if count < 2:
            continue
        first_id = next(element_id for element_id, value in texts if value == text)
        failures.append(
            ValidationFailure(
                code="DUPLICATE_PARAGRAPHS",
                message="Heading or paragraph text is duplicated on the page.",
                element_id=first_id,
                details={"occurrences": count},
            )
        )
    return failures


def _inside_page(
    left: float,
    top: float,
    right: float,
    bottom: float,
    width: float,
    height: float,
) -> bool:
    return (
        left >= -BBOX_TOLERANCE
        and top >= -BBOX_TOLERANCE
        and right <= width + BBOX_TOLERANCE
        and bottom <= height + BBOX_TOLERANCE
    )


def _reading_order_inversions(elements: list[CanonicalElement]) -> float:
    located = [element for element in elements if element.bbox is not None]
    if len(located) < 2:
        return 0.0
    geometric = sorted(located, key=lambda element: (round(element.bbox.top, 1), element.bbox.left))
    pairs = 0
    inversions = 0
    for left_index, left in enumerate(geometric):
        for right in geometric[left_index + 1 :]:
            pairs += 1
            if left.reading_order > right.reading_order:
                inversions += 1
    return inversions / pairs if pairs else 0.0


def _normalize(text: str | None) -> str:
    return " ".join((text or "").split()).lower()
