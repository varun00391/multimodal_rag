"""Standalone region detection (blueprint Step 5).

Input: native PDF objects (Step 4) plus table boxes from PyMuPDF.
Output: typed regions used for routing — heading, paragraph, table, diagram, ...

This is classification of areas, not final extraction of their content.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from native_extractor import NativeObject, pdf_bbox_to_px
from pdf_profiler import PageProfile

HEADING_MAX_CHARS = 140
LIST_RE = re.compile(r"^\s*(?:[-*•●▪‣]|(\d+|[A-Za-z])[.)])\s+")
FOOTNOTE_RE = re.compile(r"^\s*(?:\d+|[ivxlcdm]+)[.)]\s+", re.I)
CAPTION_RE = re.compile(r"^\s*(figure|fig\.|table|chart)\s", re.I)

MIN_DRAWINGS_FOR_DIAGRAM = 12
DRAWING_CLUSTER_GAP = 18.0
FULL_PAGE_COVER = 0.85


@dataclass
class Region:
    id: str
    type: str
    page: int
    bbox: list[float]
    bbox_pdf: list[float]
    source: str
    native_object_ids: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)
    engines: list[str] = field(default_factory=list)


def region_to_dict(region: Region) -> dict[str, Any]:
    return asdict(region)


def find_table_bboxes(page) -> list[list[float]]:
    try:
        finder = page.find_tables()
    except Exception:
        return []
    tables = getattr(finder, "tables", finder) or []
    bboxes: list[list[float]] = []
    for table in tables:
        bbox = getattr(table, "bbox", None)
        if bbox is None:
            continue
        bboxes.append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])])
    return bboxes


def detect_regions(
    page_profile: PageProfile,
    native_objects: list[NativeObject],
    dpi: int,
    table_bboxes_pdf: list[list[float]] | None = None,
) -> list[Region]:
    table_bboxes_pdf = table_bboxes_pdf or []
    regions: list[Region] = []
    index = 0
    page_number = page_profile.page_number
    page_area = max(1.0, page_profile.width * page_profile.height)

    for table_bbox in table_bboxes_pdf:
        index += 1
        regions.append(
            Region(
                id=_rid(page_number, index),
                type="table",
                page=page_number,
                bbox=pdf_bbox_to_px(table_bbox, dpi),
                bbox_pdf=table_bbox,
                source="pymupdf.table",
            )
        )

    for obj in native_objects:
        if obj.type != "image":
            continue
        if _overlaps_any(obj.bbox_pdf or obj.bbox, table_bboxes_pdf):
            continue
        index += 1
        regions.append(
            Region(
                id=_rid(page_number, index),
                type=_visual_type(obj, page_profile),
                page=page_number,
                bbox=obj.bbox,
                bbox_pdf=obj.bbox_pdf or obj.bbox,
                source="pymupdf.image",
                native_object_ids=[obj.id],
            )
        )

    for cluster_ids, cluster_bbox in _drawing_clusters(native_objects, page_area):
        if _overlaps_any(cluster_bbox, table_bboxes_pdf, threshold=0.5):
            continue
        index += 1
        regions.append(
            Region(
                id=_rid(page_number, index),
                type="diagram",
                page=page_number,
                bbox=pdf_bbox_to_px(cluster_bbox, dpi),
                bbox_pdf=cluster_bbox,
                source="pymupdf.drawings",
                native_object_ids=cluster_ids,
                extra={"drawing_count": len(cluster_ids)},
            )
        )

    text_blocks = [obj for obj in native_objects if obj.type == "block"]
    if not text_blocks:
        text_blocks = [obj for obj in native_objects if obj.type in {"line", "text"}]

    for obj in text_blocks:
        if _overlaps_any(obj.bbox_pdf or obj.bbox, table_bboxes_pdf, threshold=0.5):
            continue
        index += 1
        text = _object_text(obj)
        regions.append(
            Region(
                id=_rid(page_number, index),
                type=_classify_text_block(obj, page_profile, text),
                page=page_number,
                bbox=obj.bbox,
                bbox_pdf=obj.bbox_pdf or obj.bbox,
                source="pymupdf.block",
                native_object_ids=[obj.id],
                extra={"text": text[:500]},
            )
        )

    if page_profile.is_probably_scanned and not regions:
        index += 1
        full = page_profile.mediabox or [0.0, 0.0, page_profile.width, page_profile.height]
        regions.append(
            Region(
                id=_rid(page_number, index),
                type="paragraph",
                page=page_number,
                bbox=pdf_bbox_to_px(full, dpi),
                bbox_pdf=full,
                source="full_page_scan",
                extra={"scanned": True},
            )
        )
    return regions


def count_region_types(regions: list[Region]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for region in regions:
        counts[region.type] = counts.get(region.type, 0) + 1
    return counts


def _classify_text_block(obj: NativeObject, page_profile: PageProfile, text: str) -> str:
    extra = obj.extra or {}
    font_size = float(extra.get("font_size") or extra.get("size") or 0)
    bbox = obj.bbox_pdf or obj.bbox
    y0 = bbox[1] if len(bbox) == 4 else 0
    y1 = bbox[3] if len(bbox) == 4 else 0
    page_h = page_profile.height or 1
    if y1 < page_h * 0.08 and len(text) < 80:
        return "header"
    if y0 > page_h * 0.92 and len(text) < 80:
        return "footer"
    if y0 > page_h * 0.82 and FOOTNOTE_RE.match(text) and font_size and font_size < 10:
        return "footnote"
    if CAPTION_RE.match(text):
        return "caption"
    if LIST_RE.match(text):
        return "list"
    avg_size = float(extra.get("page_avg_font") or 11.0)
    if font_size >= max(14.0, avg_size * 1.25) and len(text) <= HEADING_MAX_CHARS:
        return "heading"
    if len(text) <= 60 and extra.get("is_bold") and font_size >= avg_size:
        return "heading"
    return "paragraph"


def _visual_type(obj: NativeObject, page_profile: PageProfile) -> str:
    extra = obj.extra or {}
    width = extra.get("width") or 0
    height = extra.get("height") or 0
    if page_profile.vector_count > 80 and width and height:
        return "chart" if width >= height else "diagram"
    return "image"


def _drawing_clusters(
    native_objects: list[NativeObject],
    page_area: float,
) -> list[tuple[list[str], list[float]]]:
    drawings = [obj for obj in native_objects if obj.type == "drawing"]
    if len(drawings) < MIN_DRAWINGS_FOR_DIAGRAM:
        return []

    n = len(drawings)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    boxes = [obj.bbox_pdf for obj in drawings]
    for i in range(n):
        for j in range(i + 1, n):
            if _near(boxes[i], boxes[j], DRAWING_CLUSTER_GAP):
                union(i, j)

    grouped: dict[int, list[NativeObject]] = {}
    for i, obj in enumerate(drawings):
        grouped.setdefault(find(i), []).append(obj)

    results: list[tuple[list[str], list[float]]] = []
    for group in grouped.values():
        if len(group) < MIN_DRAWINGS_FOR_DIAGRAM:
            continue
        bbox = _union_boxes([obj.bbox_pdf for obj in group])
        area = max(0.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
        if area / page_area >= FULL_PAGE_COVER:
            continue
        results.append(([obj.id for obj in group], bbox))
    return results


def _object_text(obj: NativeObject) -> str:
    if isinstance(obj.content, str):
        return obj.content.strip()
    if isinstance(obj.content, dict):
        return str(obj.content.get("text") or "").strip()
    return ""


def _rid(page_number: int, index: int) -> str:
    return f"r_p{page_number}_{index}"


def _as_box(seq: list[float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _box_area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection_area(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _iou(a: list[float], b: list[float]) -> float:
    aa, bb = _as_box(a), _as_box(b)
    inter = _intersection_area(aa, bb)
    if inter <= 0:
        return 0.0
    union = _box_area(aa) + _box_area(bb) - inter
    return inter / union if union else 0.0


def _overlaps_any(box: list[float], bboxes: list[list[float]], threshold: float = 0.35) -> bool:
    if not box or len(box) < 4:
        return False
    for other in bboxes:
        if _iou(box, other) >= threshold:
            return True
    return False


def _near(a: list[float], b: list[float], gap: float) -> bool:
    aa, bb = _as_box(a), _as_box(b)
    expanded = (aa[0] - gap, aa[1] - gap, aa[2] + gap, aa[3] + gap)
    return _intersection_area(expanded, bb) > 0


def _union_boxes(boxes: list[list[float]]) -> list[float]:
    valid = [box for box in boxes if box and len(box) >= 4]
    if not valid:
        return [0.0, 0.0, 0.0, 0.0]
    x0 = min(float(box[0]) for box in valid)
    y0 = min(float(box[1]) for box in valid)
    x1 = max(float(box[2]) for box in valid)
    y1 = max(float(box[3]) for box in valid)
    return [x0, y0, x1, y1]
