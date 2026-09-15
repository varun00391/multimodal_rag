from __future__ import annotations

from app.core.ids import region_id
from app.layout.region_classifier import classify_text_block
from app.models.common import RegionType, bbox_from_seq, iou, pdf_bbox_to_px
from app.models.element import NativeObject
from app.models.page import PageProfile
from app.models.region import Region


def detect_regions(
    page_number: int,
    page_profile: PageProfile,
    native_objects: list[NativeObject],
    dpi: int,
    table_bboxes_pdf: list[list[float]] | None = None,
) -> list[Region]:
    table_bboxes_pdf = table_bboxes_pdf or []
    regions: list[Region] = []
    used_native: set[str] = set()
    index = 0

    for table_bbox in table_bboxes_pdf:
        index += 1
        rid = region_id(page_number, index)
        regions.append(
            Region(
                id=rid,
                type=RegionType.TABLE,
                page=page_number,
                bbox=pdf_bbox_to_px(table_bbox, dpi),
                bbox_pdf=table_bbox,
                source="pymupdf.table",
            )
        )

    image_objects = [obj for obj in native_objects if obj.type == "image"]
    for obj in image_objects:
        obj_box = bbox_from_seq(obj.bbox_pdf or obj.bbox)
        if _overlaps_any(obj_box, table_bboxes_pdf):
            continue
        index += 1
        used_native.add(obj.id)
        region_type = _visual_type(obj, page_profile)
        regions.append(
            Region(
                id=region_id(page_number, index),
                type=region_type,
                page=page_number,
                bbox=obj.bbox,
                bbox_pdf=obj.bbox_pdf or obj.bbox,
                source="pymupdf.image",
                native_object_ids=[obj.id],
            )
        )

    text_blocks = [obj for obj in native_objects if obj.type == "block"]
    if not text_blocks:
        text_blocks = [obj for obj in native_objects if obj.type in {"line", "text"}]

    for obj in text_blocks:
        obj_box = bbox_from_seq(obj.bbox_pdf or obj.bbox)
        if _overlaps_any(obj_box, table_bboxes_pdf, threshold=0.5):
            used_native.add(obj.id)
            continue
        index += 1
        used_native.add(obj.id)
        region_type = classify_text_block(obj, page_profile)
        regions.append(
            Region(
                id=region_id(page_number, index),
                type=region_type,
                page=page_number,
                bbox=obj.bbox,
                bbox_pdf=obj.bbox_pdf or obj.bbox,
                source="pymupdf.block",
                native_object_ids=[obj.id],
                extra={"text": _object_text(obj)},
            )
        )

    if page_profile.is_probably_scanned and not regions:
        index += 1
        full = page_profile.mediabox or [0, 0, page_profile.width, page_profile.height]
        regions.append(
            Region(
                id=region_id(page_number, index),
                type=RegionType.PARAGRAPH,
                page=page_number,
                bbox=pdf_bbox_to_px(full, dpi),
                bbox_pdf=full,
                source="full_page_scan",
                extra={"scanned": True},
            )
        )
    return regions


def _object_text(obj: NativeObject) -> str:
    if isinstance(obj.content, str):
        return obj.content
    if isinstance(obj.content, dict):
        return str(obj.content.get("text") or "")
    return ""


def _overlaps_any(box, bboxes: list[list[float]], threshold: float = 0.35) -> bool:
    from app.models.common import bbox_from_seq as to_box

    a = box if hasattr(box, "area") else to_box(box)
    for other in bboxes:
        if iou(a, to_box(other)) >= threshold:
            return True
    return False


def _visual_type(obj: NativeObject, page_profile: PageProfile) -> RegionType:
    extra = obj.extra or {}
    width = extra.get("width") or 0
    height = extra.get("height") or 0
    if page_profile.vector_count > 80 and width and height:
        return RegionType.CHART if width >= height else RegionType.DIAGRAM
    if extra.get("is_mask"):
        return RegionType.IMAGE
    return RegionType.IMAGE
