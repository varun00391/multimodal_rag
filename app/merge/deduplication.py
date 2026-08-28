from __future__ import annotations

from app.merge.coordinates import bbox_iou, containment_ratio
from app.models.canonical import CanonicalElement, ElementType

TEXT_TYPES = {
    ElementType.HEADING,
    ElementType.PARAGRAPH,
    ElementType.LIST,
    ElementType.HEADER,
    ElementType.FOOTER,
    ElementType.FOOTNOTE,
    ElementType.PAGE_NUMBER,
}
TABLE_PRECEDENCE = {"docling": 3, "gemini": 2, "pymupdf": 1}
STRUCTURE_PRECEDENCE = {"docling": 3, "gemini": 2, "pymupdf": 1}
TEXT_PRECEDENCE = {"pymupdf": 3, "docling": 2, "gemini": 1}
IOU_THRESHOLD = 0.50
TABLE_TEXT_CONTAINMENT = 0.70


def deduplicate_elements(elements: list[CanonicalElement]) -> tuple[list[CanonicalElement], list[str]]:
    remaining = list(elements)
    warnings: list[str] = []
    remaining, dropped_table_text = _drop_text_inside_tables(remaining)
    warnings.extend(dropped_table_text)
    remaining, dropped_overlaps = _drop_overlapping_same_type(remaining)
    warnings.extend(dropped_overlaps)
    remaining, dropped_text = _drop_duplicate_text(remaining)
    warnings.extend(dropped_text)
    return remaining, warnings


def _drop_text_inside_tables(
    elements: list[CanonicalElement],
) -> tuple[list[CanonicalElement], list[str]]:
    tables = [element for element in elements if element.type == ElementType.TABLE and element.bbox]
    if not tables:
        return elements, []
    kept: list[CanonicalElement] = []
    warnings: list[str] = []
    for element in elements:
        if element.type == ElementType.TABLE or element.bbox is None or element.type not in TEXT_TYPES:
            kept.append(element)
            continue
        table = next(
            (
                item
                for item in tables
                if containment_ratio(element.bbox, item.bbox) >= TABLE_TEXT_CONTAINMENT
                and _text_covered_by(element, item)
            ),
            None,
        )
        if table is None:
            kept.append(element)
            continue
        _remember_duplicate(table, element)
        warnings.append(
            "Dropped duplicate table text from "
            f"{_extractor_name(element)} while keeping surrounding non-table content."
        )
    return kept, warnings


def _drop_overlapping_same_type(
    elements: list[CanonicalElement],
) -> tuple[list[CanonicalElement], list[str]]:
    suppressed: set[int] = set()
    warnings: list[str] = []
    for index, element in enumerate(elements):
        if index in suppressed:
            continue
        winner_index = index
        for other_index in range(index + 1, len(elements)):
            if other_index in suppressed:
                continue
            winner = elements[winner_index]
            other = elements[other_index]
            if not _same_merge_group(winner, other):
                continue
            if winner.bbox is None or other.bbox is None:
                continue
            if bbox_iou(winner.bbox, other.bbox) < IOU_THRESHOLD:
                continue
            if _precedence(other) > _precedence(winner):
                _remember_duplicate(other, winner)
                warnings.append(_conflict_warning(winner, other, kept_name=_extractor_name(other)))
                suppressed.add(winner_index)
                winner_index = other_index
            else:
                _remember_duplicate(winner, other)
                warnings.append(_conflict_warning(other, winner, kept_name=_extractor_name(winner)))
                suppressed.add(other_index)
    kept = [element for index, element in enumerate(elements) if index not in suppressed]
    return kept, warnings


def _drop_duplicate_text(
    elements: list[CanonicalElement],
) -> tuple[list[CanonicalElement], list[str]]:
    seen: dict[tuple[ElementType, str], CanonicalElement] = {}
    kept: list[CanonicalElement] = []
    warnings: list[str] = []
    for element in elements:
        key_text = _normalize_text(element.text)
        if element.type not in TEXT_TYPES or not key_text:
            kept.append(element)
            continue
        key = (element.type, key_text)
        existing = seen.get(key)
        if existing is None:
            seen[key] = element
            kept.append(element)
            continue
        if _precedence(element) > _precedence(existing):
            _remember_duplicate(element, existing)
            kept = [item for item in kept if item is not existing]
            kept.append(element)
            seen[key] = element
            warnings.append(
                f"Dropped duplicate {_extractor_name(existing)} {element.type.value} text."
            )
        else:
            _remember_duplicate(existing, element)
            warnings.append(
                f"Dropped duplicate {_extractor_name(element)} {element.type.value} text."
            )
    return kept, warnings


def _same_merge_group(left: CanonicalElement, right: CanonicalElement) -> bool:
    if left.type == right.type:
        return True
    if {left.type, right.type} <= {ElementType.PARAGRAPH, ElementType.HEADING, ElementType.LIST}:
        return _normalize_text(left.text) == _normalize_text(right.text) and bool(_normalize_text(left.text))
    return False


def _text_covered_by(element: CanonicalElement, table: CanonicalElement) -> bool:
    snippet = _normalize_text(element.text)
    if not snippet:
        return True
    haystack = " ".join(
        part
        for part in (
            _normalize_text(table.text),
            _normalize_text(table.markdown),
            _normalize_text(table.html),
        )
        if part
    )
    if not haystack:
        return True
    return snippet in haystack or _token_overlap(snippet, haystack) >= 0.6


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


def _precedence(element: CanonicalElement) -> int:
    extractor = _extractor_name(element)
    if element.type == ElementType.TABLE:
        return TABLE_PRECEDENCE.get(extractor, 0)
    if element.type in {ElementType.FORMULA, ElementType.CODE}:
        return STRUCTURE_PRECEDENCE.get(extractor, 0)
    return TEXT_PRECEDENCE.get(extractor, 0)


def _extractor_name(element: CanonicalElement) -> str:
    if element.extractor and element.extractor.name:
        return element.extractor.name
    return "unknown"


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").split()).lower()


def _remember_duplicate(winner: CanonicalElement, dropped: CanonicalElement) -> None:
    sources = list(winner.metadata.get("duplicate_sources") or [])
    sources.append(
        {
            "extractor": _extractor_name(dropped),
            "type": dropped.type.value,
            "text": (dropped.text or "")[:500],
            "element_id": dropped.element_id,
        }
    )
    winner.metadata["duplicate_sources"] = sources


def _conflict_warning(dropped: CanonicalElement, kept: CanonicalElement, *, kept_name: str) -> str:
    dropped_name = _extractor_name(dropped)
    if _normalize_text(dropped.text) and _normalize_text(dropped.text) != _normalize_text(kept.text):
        return (
            f"Conflicting overlapping {dropped.type.value} claims: kept {kept_name}, "
            f"recorded {dropped_name} text in diagnostics."
        )
    return f"Dropped duplicate {dropped_name} {dropped.type.value} overlapping {kept_name} output."
