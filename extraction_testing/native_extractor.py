"""Standalone native PDF extraction (blueprint Step 4).

Pulls PDF-native objects with PyMuPDF: words, lines, spans, blocks,
images, drawings, links, annotations. This is an inventory, not region
classification.

Each object keeps id, page, bbox (pixels + PDF points), content, type,
and source=pymupdf.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pdf_profiler import PageProfile, open_pdf

BOLD_FLAG = 2**4


@dataclass
class NativeObject:
    id: str
    type: str
    page: int
    bbox: list[float]
    bbox_pdf: list[float]
    content: Any = None
    source: str = "pymupdf"
    extra: dict[str, Any] = field(default_factory=dict)


def pdf_bbox_to_px(bbox: list[float], dpi: int) -> list[float]:
    scale = dpi / 72.0
    return [round(float(v) * scale, 2) for v in bbox]


def native_to_dict(obj: NativeObject) -> dict[str, Any]:
    return asdict(obj)


def extract_native_page(page, page_number: int, dpi: int) -> list[NativeObject]:
    objects: list[NativeObject] = []
    counter = 0
    text_dict = page.get_text("dict") or {}
    avg_font = _average_font_size(text_dict)

    for block in text_dict.get("blocks", []):
        bbox = _as_bbox(block.get("bbox"))
        counter += 1
        if block.get("type") == 0:
            lines_text: list[str] = []
            sizes: list[float] = []
            flags: list[int] = []
            for line in block.get("lines", []):
                span_text = "".join(span.get("text", "") for span in line.get("spans", []))
                lines_text.append(span_text)
                for span in line.get("spans", []):
                    sizes.append(float(span.get("size") or 0))
                    flags.append(int(span.get("flags") or 0))
            text = "\n".join(lines_text).strip()
            objects.append(
                NativeObject(
                    id=_oid("block", page_number, counter),
                    type="block",
                    page=page_number,
                    bbox=pdf_bbox_to_px(bbox, dpi),
                    bbox_pdf=bbox,
                    content=text,
                    extra={
                        "font_size": max(sizes) if sizes else 0,
                        "page_avg_font": avg_font,
                        "is_bold": any(flag & BOLD_FLAG for flag in flags),
                    },
                )
            )
            line_index = 0
            span_index = 0
            for line in block.get("lines", []):
                line_index += 1
                line_bbox = _as_bbox(line.get("bbox"), bbox)
                line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                objects.append(
                    NativeObject(
                        id=_oid("line", page_number, counter * 100 + line_index),
                        type="line",
                        page=page_number,
                        bbox=pdf_bbox_to_px(line_bbox, dpi),
                        bbox_pdf=line_bbox,
                        content=line_text,
                    )
                )
                for span in line.get("spans", []):
                    span_index += 1
                    span_bbox = _as_bbox(span.get("bbox"), line_bbox)
                    objects.append(
                        NativeObject(
                            id=_oid("span", page_number, counter * 1000 + span_index),
                            type="span",
                            page=page_number,
                            bbox=pdf_bbox_to_px(span_bbox, dpi),
                            bbox_pdf=span_bbox,
                            content=span.get("text", ""),
                            extra={
                                "font": span.get("font"),
                                "size": float(span.get("size") or 0),
                                "flags": int(span.get("flags") or 0),
                                "is_bold": bool(int(span.get("flags") or 0) & BOLD_FLAG),
                            },
                        )
                    )
        elif block.get("type") == 1:
            objects.append(
                NativeObject(
                    id=_oid("image_block", page_number, counter),
                    type="image_block",
                    page=page_number,
                    bbox=pdf_bbox_to_px(bbox, dpi),
                    bbox_pdf=bbox,
                    extra={
                        "width": block.get("width"),
                        "height": block.get("height"),
                    },
                )
            )

    for word in page.get_text("words") or []:
        bbox = [float(word[0]), float(word[1]), float(word[2]), float(word[3])]
        counter += 1
        objects.append(
            NativeObject(
                id=_oid("text", page_number, counter),
                type="text",
                page=page_number,
                bbox=pdf_bbox_to_px(bbox, dpi),
                bbox_pdf=bbox,
                content=str(word[4]),
                extra={
                    "block_no": int(word[5]) if len(word) > 5 else None,
                    "line_no": int(word[6]) if len(word) > 6 else None,
                    "word_no": int(word[7]) if len(word) > 7 else None,
                },
            )
        )

    for image in page.get_images(full=True) or []:
        xref = image[0]
        counter += 1
        bbox = [0.0, 0.0, 0.0, 0.0]
        try:
            rects = list(page.get_image_rects(xref) or [])
        except Exception:
            rects = []
        if rects:
            rect = rects[0]
            bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
        objects.append(
            NativeObject(
                id=_oid("image", page_number, counter),
                type="image",
                page=page_number,
                bbox=pdf_bbox_to_px(bbox, dpi),
                bbox_pdf=bbox,
                extra={
                    "xref": xref,
                    "width": image[2] if len(image) > 2 else None,
                    "height": image[3] if len(image) > 3 else None,
                },
            )
        )

    for drawing in page.get_drawings() or []:
        rect = drawing.get("rect")
        if rect is None:
            continue
        bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
        counter += 1
        objects.append(
            NativeObject(
                id=_oid("drawing", page_number, counter),
                type="drawing",
                page=page_number,
                bbox=pdf_bbox_to_px(bbox, dpi),
                bbox_pdf=bbox,
                extra={"items": len(drawing.get("items") or [])},
            )
        )

    for link in page.get_links() or []:
        rect = link.get("from")
        if rect is None:
            continue
        bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
        counter += 1
        objects.append(
            NativeObject(
                id=_oid("link", page_number, counter),
                type="link",
                page=page_number,
                bbox=pdf_bbox_to_px(bbox, dpi),
                bbox_pdf=bbox,
                content=link.get("uri") or link.get("page"),
                extra={"kind": link.get("kind")},
            )
        )

    for annot in page.annots() or []:
        rect = annot.rect
        bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
        counter += 1
        info = annot.info or {}
        annot_type = annot.type[1] if annot.type else None
        objects.append(
            NativeObject(
                id=_oid("annot", page_number, counter),
                type="annotation",
                page=page_number,
                bbox=pdf_bbox_to_px(bbox, dpi),
                bbox_pdf=bbox,
                content=info.get("content"),
                extra={"type": annot_type},
            )
        )
    return objects


def extract_native_document(
    pdf_path: str | Path,
    dpi: int,
) -> dict[int, list[NativeObject]]:
    path = Path(pdf_path)
    doc = open_pdf(path)
    try:
        return {
            index + 1: extract_native_page(doc.load_page(index), index + 1, dpi)
            for index in range(doc.page_count)
        }
    finally:
        doc.close()


def extract_native_and_detect_regions(
    pdf_path: str | Path,
    pages: list[PageProfile],
    dpi: int,
) -> tuple[dict[int, list[NativeObject]], dict[int, list[Any]]]:
    """Open the PDF once for Step 4 (native) and Step 5 (regions)."""
    from region_detector import detect_regions, find_table_bboxes
    from region_tree import build_region_tree

    path = Path(pdf_path)
    native_by_page: dict[int, list[NativeObject]] = {}
    regions_by_page: dict[int, list[Any]] = {}
    doc = open_pdf(path)
    try:
        for page_profile in pages:
            page = doc.load_page(page_profile.page_number - 1)
            native = extract_native_page(page, page_profile.page_number, dpi)
            table_bboxes = find_table_bboxes(page)
            regions = detect_regions(page_profile, native, dpi, table_bboxes)
            regions = build_region_tree(regions)
            native_by_page[page_profile.page_number] = native
            regions_by_page[page_profile.page_number] = regions
    finally:
        doc.close()
    return native_by_page, regions_by_page


def count_native_types(objects: list[NativeObject]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for obj in objects:
        counts[obj.type] = counts.get(obj.type, 0) + 1
    return counts


def _oid(kind: str, page_number: int, index: int) -> str:
    return f"native_{kind}_p{page_number}_{index}"


def _as_bbox(raw: Any, fallback: list[float] | None = None) -> list[float]:
    if raw is not None and len(raw) >= 4:
        return [float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3])]
    return list(fallback or [0.0, 0.0, 0.0, 0.0])


def _average_font_size(text_dict: dict) -> float:
    sizes: list[float] = []
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("size"):
                    sizes.append(float(span["size"]))
    return sum(sizes) / len(sizes) if sizes else 11.0
