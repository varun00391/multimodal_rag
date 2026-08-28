from __future__ import annotations

from app.merge.coordinates import bbox_iou, containment_ratio, normalize_bbox
from app.merge.deduplication import deduplicate_elements
from app.models.canonical import CanonicalElement, CanonicalPage, ElementType
from app.models.inspection import DocumentInspection, PageInspection

TABLE_REASON_CODES = {"TABLE_STRUCTURE_INVALID", "TABLE_EMPTY"}
FORMULA_REASON_CODES = {"FORMULA_MISSING"}
VISUAL_REASON_CODES = {"VISUAL_MEANING_MISSING"}
VISUAL_TYPES = {ElementType.PICTURE, ElementType.CHART, ElementType.DIAGRAM}


def finalize_pages(
    pages: list[CanonicalPage],
    inspection: DocumentInspection,
) -> list[CanonicalPage]:
    by_inspection = {page.page: page for page in inspection.pages}
    return [
        finalize_page(page, by_inspection.get(page.page), document_id=inspection.document_id)
        for page in pages
    ]


def finalize_page(
    page: CanonicalPage,
    inspection: PageInspection | None,
    *,
    document_id: str,
) -> CanonicalPage:
    width = inspection.width if inspection is not None else page.width
    height = inspection.height if inspection is not None else page.height
    rotation = inspection.rotation if inspection is not None else page.rotation
    normalized = [
        _normalize_element(element, width, height, page.page) for element in page.elements
    ]
    attached, attach_warnings = attach_visual_semantics(normalized)
    deduped, warnings = deduplicate_elements(attached)
    warnings = list(attach_warnings) + list(warnings)
    ordered = _assign_reading_order(deduped, document_id, page.page)
    merged_warnings = list(dict.fromkeys([*page.warnings, *warnings]))
    attempts = list(page.attempts)
    for index, attempt in enumerate(attempts, start=1):
        attempt.attempt = index
    page.width = width
    page.height = height
    page.rotation = rotation
    page.elements = ordered
    page.warnings = merged_warnings
    page.attempts = attempts
    page.extraction_routes = list(dict.fromkeys(page.extraction_routes))
    return page


def absorb_fallback(
    original: CanonicalPage,
    fallback: CanonicalPage,
    reason_code: str,
) -> CanonicalPage:
    if reason_code in TABLE_REASON_CODES:
        kept = [element for element in original.elements if element.type != ElementType.TABLE]
        added = [element for element in fallback.elements if element.type == ElementType.TABLE]
        original.elements = kept + (added or list(fallback.elements))
    elif reason_code in FORMULA_REASON_CODES:
        added = [
            element
            for element in fallback.elements
            if element.type in {ElementType.FORMULA, ElementType.CODE}
        ]
        original.elements = list(original.elements) + (added or list(fallback.elements))
    elif reason_code in VISUAL_REASON_CODES:
        original.elements, _warnings = attach_visual_semantics(
            list(original.elements) + list(fallback.elements)
        )
        original.warnings.extend(_warnings)
    else:
        original.elements = list(fallback.elements)

    original.attempts.extend(fallback.attempts)
    original.warnings.extend(fallback.warnings)
    original.errors = [
        error
        for error in original.errors
        if error.code != reason_code
    ]
    original.errors.extend(
        error for error in fallback.errors if error.code not in {item.code for item in original.errors}
    )
    for route in fallback.extraction_routes:
        if route and route not in original.extraction_routes:
            original.extraction_routes.append(route)
    if fallback.primary_route and reason_code not in TABLE_REASON_CODES | FORMULA_REASON_CODES | VISUAL_REASON_CODES:
        original.primary_route = fallback.primary_route
    original.routing_reasons.append(f"Fallback applied for {reason_code}")
    return original


def _normalize_element(
    element: CanonicalElement,
    page_width: float,
    page_height: float,
    page_number: int,
) -> CanonicalElement:
    updated = element.model_copy(deep=True)
    updated.page = page_number
    if updated.bbox is not None:
        updated.bbox = normalize_bbox(updated.bbox, page_width, page_height)
    if updated.provenance is not None:
        updated.provenance.source_page = page_number
        updated.provenance.source_coordinate_system = "pdf-points-top-left"
    return updated


def _assign_reading_order(
    elements: list[CanonicalElement],
    document_id: str,
    page_number: int,
) -> list[CanonicalElement]:
    ordered = sorted(elements, key=_reading_key)
    assigned: list[CanonicalElement] = []
    for index, element in enumerate(ordered, start=1):
        updated = element.model_copy(deep=True)
        updated.reading_order = index
        updated.element_id = f"{document_id}:p{page_number}:e{index}"
        if updated.provenance is not None:
            updated.provenance.attempt = updated.provenance.attempt or 1
        assigned.append(updated)
    return assigned


def _reading_key(element: CanonicalElement) -> tuple[float, float, int]:
    if element.bbox is not None:
        return (round(element.bbox.top, 1), element.bbox.left, element.reading_order)
    return (float(element.reading_order), 0.0, element.reading_order)


def attach_visual_semantics(
    elements: list[CanonicalElement],
) -> tuple[list[CanonicalElement], list[str]]:
    groq_items = [
        element
        for element in elements
        if _extractor_name(element) == "groq-vision" and element.type in VISUAL_TYPES
    ]
    if not groq_items:
        return elements, []
    others = [element for element in elements if element not in groq_items]
    warnings: list[str] = []
    unmatched: list[CanonicalElement] = []
    for groq_element in groq_items:
        match = _best_visual_match(groq_element, others)
        if match is None:
            unmatched.append(groq_element)
            continue
        if groq_element.text:
            match.text = groq_element.text
            match.markdown = groq_element.markdown or groq_element.text
        if groq_element.type in {ElementType.CHART, ElementType.DIAGRAM}:
            match.type = groq_element.type
        if groq_element.asset and not match.asset:
            match.asset = groq_element.asset
        match.metadata = {
            **match.metadata,
            "visual_semantics": {
                "extractor": "groq-vision",
                "title": (groq_element.metadata or {}).get("title"),
                "caption": (groq_element.metadata or {}).get("caption"),
                "uncertain": (groq_element.metadata or {}).get("uncertain"),
            },
        }
        warnings.append(
            f"Attached Groq vision description to existing {match.type.value} element."
        )
    return others + unmatched, warnings


def _best_visual_match(
    groq_element: CanonicalElement,
    candidates: list[CanonicalElement],
) -> CanonicalElement | None:
    if groq_element.bbox is None:
        return None
    best: CanonicalElement | None = None
    best_score = 0.0
    for candidate in candidates:
        if candidate.type not in VISUAL_TYPES or candidate.bbox is None:
            continue
        score = max(
            bbox_iou(groq_element.bbox, candidate.bbox),
            containment_ratio(groq_element.bbox, candidate.bbox),
            containment_ratio(candidate.bbox, groq_element.bbox),
        )
        if score > best_score:
            best = candidate
            best_score = score
    return best if best_score >= 0.30 else None


def _extractor_name(element: CanonicalElement) -> str:
    if element.extractor and element.extractor.name:
        return element.extractor.name
    return "unknown"

