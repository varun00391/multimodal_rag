from __future__ import annotations

import asyncio
import re
import time
from collections import Counter
from pathlib import Path

import fitz

from app.config import Settings
from app.inspection.features import LIST_LINE_PATTERN, looks_like_list_line
from app.merge.coordinates import rect_to_bbox
from app.models.canonical import (
    CanonicalElement,
    CanonicalExtractionResult,
    CanonicalPage,
    ElementProvenance,
    ElementType,
    ExtractionAttempt,
    ExtractorProvenance,
)
from app.models.routing import ExtractionTask

ADAPTER_VERSION = "1.0.0"


def _pymupdf_version() -> str | None:
    if hasattr(fitz, "version") and fitz.version:
        parts = fitz.version[:2]
        return ".".join(str(part) for part in parts)
    return None


class PyMuPDFAdapter:
    name = "pymupdf"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def extract(
        self,
        pdf_path: Path,
        pages: list[int],
        tasks: list[ExtractionTask],
        context_pages: list[int] | None = None,
    ) -> CanonicalExtractionResult:
        started = time.perf_counter()
        result = await asyncio.to_thread(self._extract_sync, pdf_path, pages)
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        return result

    def _extract_sync(self, pdf_path: Path, pages: list[int]) -> CanonicalExtractionResult:
        document = fitz.open(pdf_path)
        extracted_pages: list[CanonicalPage] = []
        warnings: list[str] = []
        try:
            for page_number in pages:
                page = document.load_page(page_number - 1)
                extracted_pages.append(
                    self._extract_page(
                        document=document,
                        page=page,
                        page_number=page_number,
                        document_id=pdf_path.parent.name,
                    )
                )
        finally:
            document.close()

        attempt = ExtractionAttempt(
            attempt=1,
            extractor=self.name,
            status="completed",
            element_count=sum(len(page.elements) for page in extracted_pages),
        )
        return CanonicalExtractionResult(pages=extracted_pages, attempts=[attempt], warnings=warnings)

    def _extract_page(
        self,
        *,
        document: fitz.Document,
        page: fitz.Page,
        page_number: int,
        document_id: str,
    ) -> CanonicalPage:
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])
        text_blocks = [block for block in blocks if block.get("type") == 0]
        image_blocks = [block for block in blocks if block.get("type") == 1]

        font_sizes = [
            float(span.get("size", 0.0))
            for block in text_blocks
            for line in block.get("lines", [])
            for span in line.get("spans", [])
            if span.get("size")
        ]
        median_font = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 12.0
        heading_threshold = median_font * 1.25

        elements: list[CanonicalElement] = []
        ordered_blocks: list[tuple[int, fitz.Rect, dict]] = []
        for index, block in enumerate(text_blocks):
            bbox = rect_to_bbox(block.get("bbox", (0, 0, 0, 0)))
            ordered_blocks.append((index, bbox, block))
        ordered_blocks = [
            (index, bbox, block)
            for index, bbox, block in sorted(
                ordered_blocks,
                key=lambda item: (round(item[1].top, 1), item[1].left),
            )
        ]

        reading_order = 1
        for block_index, bbox, block in ordered_blocks:
            block_text, max_font = self._block_text_and_font(block)
            if not block_text.strip():
                continue

            element_type = self._classify_block(block_text, max_font, heading_threshold)
            if element_type == ElementType.PARAGRAPH and self._table_confidence_high(block):
                element_type = ElementType.TABLE

            element = CanonicalElement(
                element_id=f"{document_id}:p{page_number}:e{reading_order}",
                type=element_type,
                page=page_number,
                reading_order=reading_order,
                text=block_text.strip(),
                markdown=self._to_markdown(element_type, block_text),
                bbox=bbox,
                confidence=0.9 if element_type != ElementType.UNKNOWN else 0.5,
                extractor=ExtractorProvenance(
                    name=self.name,
                    version=_pymupdf_version(),
                    adapter_version=ADAPTER_VERSION,
                ),
                provenance=ElementProvenance(source_page=page_number),
                metadata={"block_index": block_index},
            )
            elements.append(element)
            reading_order += 1

        for image_index, block in enumerate(image_blocks, start=1):
            bbox = rect_to_bbox(block.get("bbox", (0, 0, 0, 0)))
            asset_path = self._save_image(
                document=document,
                page=page,
                block=block,
                page_number=page_number,
                image_index=image_index,
                document_id=document_id,
            )
            elements.append(
                CanonicalElement(
                    element_id=f"{document_id}:p{page_number}:e{reading_order}",
                    type=ElementType.PICTURE,
                    page=page_number,
                    reading_order=reading_order,
                    bbox=bbox,
                    asset=asset_path,
                    confidence=0.95,
                    extractor=ExtractorProvenance(
                        name=self.name,
                        version=None,
                        adapter_version=ADAPTER_VERSION,
                    ),
                    provenance=ElementProvenance(source_page=page_number),
                )
            )
            reading_order += 1

        elements.sort(key=lambda element: (element.reading_order, element.bbox.top if element.bbox else 0))

        return CanonicalPage(
            page=page_number,
            width=page.rect.width,
            height=page.rect.height,
            rotation=page.rotation,
            primary_route=self.name,
            routing_confidence=0.9,
            overall_confidence=0.9,
            routing_reasons=["Forced PyMuPDF extraction path (Phase 2 baseline)"],
            extraction_routes=[self.name],
            elements=elements,
            attempts=[
                ExtractionAttempt(
                    attempt=1,
                    extractor=self.name,
                    status="completed",
                    element_count=len(elements),
                )
            ],
        )

    @staticmethod
    def _block_text_and_font(block: dict) -> tuple[str, float]:
        parts: list[str] = []
        font_sizes: list[float] = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                parts.append(span.get("text", ""))
                if span.get("size"):
                    font_sizes.append(float(span["size"]))
        text = "\n".join(
            "".join(span.get("text", "") for span in line.get("spans", []))
            for line in block.get("lines", [])
        )
        max_font = max(font_sizes) if font_sizes else 0.0
        return text, max_font

    @staticmethod
    def _classify_block(text: str, max_font: float, heading_threshold: float) -> ElementType:
        stripped = text.strip()
        if not stripped:
            return ElementType.UNKNOWN
        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        if len(lines) == 1 and max_font >= heading_threshold and len(stripped) < 120:
            return ElementType.HEADING
        if all(looks_like_list_line(line) for line in lines) and len(lines) >= 2:
            return ElementType.LIST
        if len(lines) >= 2 and all(LIST_LINE_PATTERN.match(line) for line in lines[:3]):
            return ElementType.LIST
        if re.match(r"^\d+$", stripped) and len(stripped) <= 4:
            return ElementType.PAGE_NUMBER
        return ElementType.PARAGRAPH

    @staticmethod
    def _table_confidence_high(block: dict) -> bool:
        lines = block.get("lines", [])
        if len(lines) < 3:
            return False
        span_counts = [len(line.get("spans", [])) for line in lines]
        if not span_counts or max(span_counts) < 3:
            return False
        return max(span_counts) - min(span_counts) <= 1

    @staticmethod
    def _to_markdown(element_type: ElementType, text: str) -> str | None:
        if element_type == ElementType.HEADING:
            return f"## {text.strip()}"
        if element_type == ElementType.LIST:
            return "\n".join(f"- {line.lstrip('•-*0123456789.) ')}" for line in text.splitlines() if line.strip())
        return None

    def _save_image(
        self,
        *,
        document: fitz.Document,
        page: fitz.Page,
        block: dict,
        page_number: int,
        image_index: int,
        document_id: str,
    ) -> str | None:
        pdf_path = Path(document.name)
        assets_dir = pdf_path.parent / "assets" / "pictures"
        assets_dir.mkdir(parents=True, exist_ok=True)
        extension = str(block.get("ext") or "png")
        filename = f"page_{page_number}_picture_{image_index}.{extension}"
        relative_path = f"assets/pictures/{filename}"
        target = assets_dir / filename

        image_bytes = block.get("image")
        if image_bytes:
            target.write_bytes(image_bytes)
            return relative_path

        try:
            bbox = block.get("bbox")
            if bbox:
                clip = fitz.Rect(bbox)
                pix = page.get_pixmap(clip=clip, alpha=False)
                target = target.with_suffix(".png")
                pix.save(target)
                return f"assets/pictures/{target.name}"
        except Exception:
            return None
        return None
