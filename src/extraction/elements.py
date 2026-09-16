from __future__ import annotations

from extraction.models.cdr import BBox, Element, Provenance, TableData


def provenance(extractor: str, version: str, model: str | None = None, prompt_version: str | None = None) -> Provenance:
    return Provenance(
        extractor=extractor,
        extractor_version=version,
        model=model,
        prompt_version=prompt_version,
    )


def element_id(unit_type: str, unit_index: int, order: int) -> str:
    return f"{unit_type}{unit_index}:e{order}"


def text_element(
    *,
    unit_type: str,
    unit_index: int,
    order: int,
    text: str,
    extractor: str,
    version: str,
    element_type: str = "paragraph",
    bbox: BBox | None = None,
    confidence: float | None = None,
    model: str | None = None,
) -> Element:
    return Element(
        element_id=element_id(unit_type, unit_index, order),
        type=element_type,
        text=text,
        bbox=bbox,
        reading_order=order,
        confidence=confidence,
        provenance=provenance(extractor, version, model=model),
    )


def table_element(
    *,
    unit_type: str,
    unit_index: int,
    order: int,
    columns: list[str],
    rows: list[list[str]],
    extractor: str,
    version: str,
    bbox: BBox | None = None,
) -> Element:
    return Element(
        element_id=element_id(unit_type, unit_index, order),
        type="table",
        table=TableData(columns=columns, rows=rows),
        bbox=bbox,
        reading_order=order,
        provenance=provenance(extractor, version),
    )


def picture_element(
    *,
    unit_type: str,
    unit_index: int,
    order: int,
    asset_path: str,
    extractor: str,
    version: str,
    text: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    bbox: BBox | None = None,
) -> Element:
    return Element(
        element_id=element_id(unit_type, unit_index, order),
        type="picture",
        text=text,
        asset_path=asset_path,
        bbox=bbox,
        reading_order=order,
        provenance=provenance(extractor, version, model=model, prompt_version=prompt_version),
    )
