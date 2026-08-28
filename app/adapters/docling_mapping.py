from __future__ import annotations

from typing import Any

from app.adapters.docling_pages import remap_page_number
from app.models.canonical import BoundingBox, CanonicalElement, ElementType

ADAPTER_VERSION = "1.0.0"

LABEL_TO_ELEMENT_TYPE: dict[str, ElementType] = {
    "title": ElementType.HEADING,
    "section_header": ElementType.HEADING,
    "paragraph": ElementType.PARAGRAPH,
    "text": ElementType.PARAGRAPH,
    "list_item": ElementType.LIST,
    "table": ElementType.TABLE,
    "picture": ElementType.PICTURE,
    "chart": ElementType.CHART,
    "formula": ElementType.FORMULA,
    "code": ElementType.CODE,
    "page_header": ElementType.HEADER,
    "page_footer": ElementType.FOOTER,
    "footnote": ElementType.FOOTNOTE,
    "caption": ElementType.PARAGRAPH,
    "key_value_region": ElementType.KEY_VALUE,
    "form": ElementType.FORM_FIELD,
    "checkbox_selected": ElementType.FORM_FIELD,
    "checkbox_unselected": ElementType.FORM_FIELD,
    "handwritten_text": ElementType.PARAGRAPH,
    "field_heading": ElementType.HEADING,
    "field_key": ElementType.KEY_VALUE,
    "field_value": ElementType.KEY_VALUE,
    "field_region": ElementType.FORM_FIELD,
    "field_item": ElementType.FORM_FIELD,
    "field_hint": ElementType.FORM_FIELD,
    "document_index": ElementType.UNKNOWN,
    "reference": ElementType.PARAGRAPH,
}


def normalize_label(label: Any) -> str:
    value = getattr(label, "value", label)
    text = str(value).strip().lower()
    prefix = "docitemlabel."
    if text.startswith(prefix):
        text = text[len(prefix) :]
    return text.replace("-", "_")


def element_type_for_label(label: Any) -> ElementType:
    return LABEL_TO_ELEMENT_TYPE.get(normalize_label(label), ElementType.UNKNOWN)


def canonical_bbox_from_docling(bbox: Any, page_height: float) -> BoundingBox | None:
    if bbox is None:
        return None

    converted = bbox
    to_top_left = getattr(bbox, "to_top_left_origin", None)
    if callable(to_top_left):
        try:
            converted = to_top_left(page_height)
        except TypeError:
            converted = to_top_left()

    origin = getattr(converted, "coord_origin", None)
    origin_value = str(getattr(origin, "value", origin) or "TOPLEFT").upper()
    left = float(getattr(converted, "l", getattr(converted, "left", 0.0)))
    top = float(getattr(converted, "t", getattr(converted, "top", 0.0)))
    right = float(getattr(converted, "r", getattr(converted, "right", 0.0)))
    bottom = float(getattr(converted, "b", getattr(converted, "bottom", 0.0)))

    if "BOTTOM" in origin_value:
        top, bottom = page_height - top, page_height - bottom

    if bottom < top:
        top, bottom = bottom, top
    if right < left:
        left, right = right, left

    return BoundingBox(left=left, top=top, right=right, bottom=bottom)


def item_label(item: Any) -> str:
    return normalize_label(getattr(item, "label", "unknown"))


def item_text(item: Any) -> str | None:
    for attr in ("text", "orig"):
        value = getattr(item, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    return None


def item_provenances(item: Any) -> list[Any]:
    prov = getattr(item, "prov", None) or []
    return list(prov)


def provenance_page_number(prov: Any, original_pages: list[int]) -> int | None:
    raw_page = getattr(prov, "page_no", getattr(prov, "page", None))
    if raw_page is None:
        return None
    return remap_page_number(int(raw_page), original_pages)


def table_exports(item: Any, document: Any | None = None) -> tuple[str | None, str | None, str | None]:
    markdown = _call_export(item, "export_to_markdown", document)
    html = _call_export(item, "export_to_html", document)
    text = item_text(item) or markdown
    return text, markdown, html


def _call_export(item: Any, method_name: str, document: Any | None) -> str | None:
    method = getattr(item, method_name, None)
    if not callable(method):
        return None
    for kwargs in ({"doc": document}, {}):
        try:
            value = method(**kwargs) if kwargs else method()
        except TypeError:
            continue
        except Exception:
            return None
        if isinstance(value, str) and value.strip():
            return value
    return None


def picture_image(item: Any, document: Any | None) -> Any | None:
    getter = getattr(item, "get_image", None)
    if not callable(getter):
        return getattr(item, "image", None)
    for kwargs in ({"doc": document}, {}):
        try:
            image = getter(**kwargs) if kwargs else getter()
        except TypeError:
            continue
        except Exception:
            return None
        if image is not None:
            return image
    return None


def iterate_document_items(document: Any):
    iterator = getattr(document, "iterate_items", None)
    if not callable(iterator):
        texts = getattr(document, "texts", []) or []
        tables = getattr(document, "tables", []) or []
        pictures = getattr(document, "pictures", []) or []
        for item in [*texts, *tables, *pictures]:
            yield item
        return

    for raw in iterator():
        yield raw[0] if isinstance(raw, tuple) else raw
