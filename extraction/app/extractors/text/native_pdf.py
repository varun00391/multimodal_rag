from __future__ import annotations

from pathlib import Path

import fitz

from app.core.config import get_settings
from app.core.ids import element_id
from app.models.common import pdf_bbox_to_px
from app.models.element import NativeObject
from app.profiling.pdf_profiler import open_pdf


def extract_native_page(page: fitz.Page, page_number: int, dpi: int | None = None) -> list[NativeObject]:
    settings = get_settings()
    dpi = dpi or settings.render_dpi
    objects: list[NativeObject] = []
    counter = 0

    text_dict = page.get_text("dict") or {}
    font_sizes: list[float] = []
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("size"):
                        font_sizes.append(float(span["size"]))
    avg_font = sum(font_sizes) / len(font_sizes) if font_sizes else 11.0

    for block in text_dict.get("blocks", []):
        bbox = [float(v) for v in block.get("bbox", [0, 0, 0, 0])]
        counter += 1
        if block.get("type") == 0:
            lines_text = []
            sizes = []
            flags = []
            for line in block.get("lines", []):
                span_text = "".join(span.get("text", "") for span in line.get("spans", []))
                lines_text.append(span_text)
                for span in line.get("spans", []):
                    sizes.append(float(span.get("size") or 0))
                    flags.append(int(span.get("flags") or 0))
            text = "\n".join(lines_text).strip()
            objects.append(
                NativeObject(
                    id=element_id("native_block", page_number, counter),
                    type="block",
                    page=page_number,
                    bbox=pdf_bbox_to_px(bbox, dpi),
                    bbox_pdf=bbox,
                    content=text,
                    extra={
                        "font_size": max(sizes) if sizes else 0,
                        "page_avg_font": avg_font,
                        "is_bold": any(flag & 2 ** 4 for flag in flags),
                    },
                )
            )
            line_index = 0
            for line in block.get("lines", []):
                line_index += 1
                line_bbox = [float(v) for v in line.get("bbox", bbox)]
                line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                objects.append(
                    NativeObject(
                        id=element_id("native_line", page_number, counter * 100 + line_index),
                        type="line",
                        page=page_number,
                        bbox=pdf_bbox_to_px(line_bbox, dpi),
                        bbox_pdf=line_bbox,
                        content=line_text,
                    )
                )
        elif block.get("type") == 1:
            objects.append(
                NativeObject(
                    id=element_id("native_image_block", page_number, counter),
                    type="image_block",
                    page=page_number,
                    bbox=pdf_bbox_to_px(bbox, dpi),
                    bbox_pdf=bbox,
                    extra={"width": block.get("width"), "height": block.get("height")},
                )
            )

    for word in page.get_text("words") or []:
        # x0, y0, x1, y1, word, block, line, word_no
        bbox = [float(word[0]), float(word[1]), float(word[2]), float(word[3])]
        counter += 1
        objects.append(
            NativeObject(
                id=element_id("native_text", page_number, counter),
                type="text",
                page=page_number,
                bbox=pdf_bbox_to_px(bbox, dpi),
                bbox_pdf=bbox,
                content=str(word[4]),
            )
        )

    for image in page.get_images(full=True) or []:
        xref = image[0]
        counter += 1
        rects = []
        try:
            rects = list(page.get_image_rects(xref) or [])
        except Exception:
            rects = []
        bbox = [0.0, 0.0, 0.0, 0.0]
        if rects:
            rect = rects[0]
            bbox = [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
        objects.append(
            NativeObject(
                id=element_id("native_image", page_number, counter),
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
                id=element_id("native_drawing", page_number, counter),
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
                id=element_id("native_link", page_number, counter),
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
        objects.append(
            NativeObject(
                id=element_id("native_annot", page_number, counter),
                type="annotation",
                page=page_number,
                bbox=pdf_bbox_to_px(bbox, dpi),
                bbox_pdf=bbox,
                content=annot.info.get("content") if annot.info else None,
                extra={"type": annot.type[1] if annot.type else None},
            )
        )
    return objects


def extract_native_document(pdf_path: Path, dpi: int | None = None) -> dict[int, list[NativeObject]]:
    doc = open_pdf(pdf_path)
    try:
        return {
            index + 1: extract_native_page(doc.load_page(index), index + 1, dpi)
            for index in range(doc.page_count)
        }
    finally:
        doc.close()
