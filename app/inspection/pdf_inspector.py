from __future__ import annotations

from pathlib import Path

import fitz

from app.config import Settings
from app.inspection.continuity import enrich_document_continuity
from app.inspection.features import (
    average_word_length,
    block_order_irregularity,
    compute_layout_complexity,
    count_words,
    coverage_ratio,
    duplicate_line_ratio,
    estimate_columns,
    looks_like_formula_or_code,
    overlap_ratio,
    printable_ratio,
    replacement_ratio,
    control_character_ratio,
)
from app.models.inspection import (
    DocumentInspection,
    ImageSignals,
    LayoutSignals,
    PageInspection,
    TextSignals,
)


class PdfInspector:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def inspect(
        self,
        pdf_path: Path,
        *,
        document_id: str,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> DocumentInspection:
        document = fitz.open(pdf_path)
        try:
            page_count = document.page_count
            start = 1 if page_start is None else page_start
            end = page_count if page_end is None else page_end
            pages: list[PageInspection] = []

            for page_number in range(start, end + 1):
                page = document.load_page(page_number - 1)
                pages.append(self._inspect_page(page, page_number))

            continuity = enrich_document_continuity(pages)
            return DocumentInspection(
                schema_version=self._settings.extraction_schema_version,
                document_id=document_id,
                page_count=page_count,
                pages=pages,
                continuity=continuity,
            )
        finally:
            document.close()

    def _inspect_page(self, page: fitz.Page, page_number: int) -> PageInspection:
        page_dict = page.get_text("dict")
        page_area = max(page.rect.width * page.rect.height, 1.0)
        text_blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0]
        image_blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 1]

        characters: list[str] = []
        lines: list[str] = []
        spans: list[dict] = []
        block_rects: list[tuple[float, float, float, float]] = []
        valid_bbox_count = 0
        font_sizes: list[float] = []
        fonts: set[str] = set()

        for block in text_blocks:
            bbox = tuple(block.get("bbox", (0, 0, 0, 0)))
            block_rects.append(bbox)
            for line in block.get("lines", []):
                line_text_parts: list[str] = []
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    characters.extend(span_text)
                    line_text_parts.append(span_text)
                    spans.append(span)
                    font_sizes.append(float(span.get("size", 0.0)))
                    fonts.add(str(span.get("font", "")))
                    span_bbox = span.get("bbox")
                    if span_bbox and span_bbox[2] > span_bbox[0] and span_bbox[3] > span_bbox[1]:
                        valid_bbox_count += 1
                line_text = "".join(line_text_parts).strip()
                if line_text:
                    lines.append(line_text)

        full_text = "".join(characters)
        character_count = len(full_text)
        word_count = count_words(full_text)
        span_count = len(spans)
        line_count = len(lines)
        block_count = len(text_blocks)

        text_coverage = 0.0
        if block_rects:
            covered = sum((rect[2] - rect[0]) * (rect[3] - rect[1]) for rect in block_rects)
            text_coverage = coverage_ratio(covered, page_area)

        font_size_distribution = {
            str(int(size)): sum(1 for value in font_sizes if int(value) == int(size))
            for size in sorted(set(font_sizes))
            if size > 0
        }

        text_signals = TextSignals(
            character_count=character_count,
            word_count=word_count,
            block_count=block_count,
            line_count=line_count,
            span_count=span_count,
            printable_ratio=round(printable_ratio(full_text), 4),
            replacement_character_ratio=round(replacement_ratio(full_text), 4),
            control_character_ratio=round(control_character_ratio(full_text), 4),
            text_coverage=round(text_coverage, 4),
            duplicate_text_ratio=round(duplicate_line_ratio(lines), 4),
            overlapping_text_ratio=round(overlap_ratio(block_rects), 4),
            valid_bbox_ratio=round(valid_bbox_count / span_count, 4) if span_count else 0.0,
            font_count=len(fonts),
            font_size_distribution=font_size_distribution,
            suspicious_hidden_ocr=character_count > 0 and text_coverage < 0.02,
            average_word_length=round(average_word_length(full_text), 4),
        )

        image_rects: list[tuple[float, float, float, float]] = []
        largest_image_area = 0.0
        total_image_area = 0.0
        max_image_width = 0.0
        max_image_height = 0.0
        for block in image_blocks:
            bbox = tuple(block.get("bbox", (0, 0, 0, 0)))
            image_rects.append(bbox)
            width = max(0.0, bbox[2] - bbox[0])
            height = max(0.0, bbox[3] - bbox[1])
            area = width * height
            total_image_area += area
            largest_image_area = max(largest_image_area, area)
            max_image_width = max(max_image_width, width)
            max_image_height = max(max_image_height, height)

        largest_image_coverage = coverage_ratio(largest_image_area, page_area)
        total_image_coverage = coverage_ratio(total_image_area, page_area)
        image_signals = ImageSignals(
            image_count=len(image_blocks),
            largest_image_coverage=round(largest_image_coverage, 4),
            total_image_coverage=round(total_image_coverage, 4),
            near_full_page_raster=largest_image_coverage >= 0.80,
            max_image_width=max_image_width,
            max_image_height=max_image_height,
            effective_resolution_dpi=self._estimate_dpi(max_image_width, max_image_height, page.rect.width),
            native_text_despite_image_coverage=character_count >= 100 and total_image_coverage >= 0.35,
        )

        drawings = page.get_drawings()
        vector_drawing_count = len(drawings)
        table_candidate_count = self._estimate_table_candidates(text_blocks)
        figure_candidate_count = sum(
            1 for block in image_blocks if coverage_ratio(self._rect_area(block.get("bbox")), page_area) >= 0.08
        )
        probable_columns = estimate_columns(block_rects, page.rect.width)
        irregular_block_order = block_order_irregularity(block_rects)
        formula_like_regions = sum(1 for line in lines if looks_like_formula_or_code(line))
        code_like_regions = sum(1 for line in lines if looks_like_formula_or_code(line) and "{" in line)

        layout_complexity = compute_layout_complexity(
            probable_columns=probable_columns,
            irregular_block_order=irregular_block_order,
            vector_drawing_count=vector_drawing_count,
            table_candidate_count=table_candidate_count,
        )
        layout_signals = LayoutSignals(
            probable_columns=probable_columns,
            irregular_block_order=round(irregular_block_order, 4),
            vector_drawing_count=vector_drawing_count,
            table_candidate_count=table_candidate_count,
            figure_candidate_count=figure_candidate_count,
            rotated_text=False,
            has_header_region=any(rect[1] < page.rect.height * 0.12 for rect in block_rects),
            has_footer_region=any(rect[3] > page.rect.height * 0.88 for rect in block_rects),
            formula_like_regions=formula_like_regions,
            code_like_regions=code_like_regions,
            layout_complexity=layout_complexity,
        )

        probable_scan = character_count < 100 and largest_image_coverage >= 0.80
        probable_complex_table = table_candidate_count >= 2 or (
            table_candidate_count >= 1 and layout_complexity >= 0.45
        )
        use_pymupdf = (
            character_count >= self._settings.pymupdf_min_characters
            and text_signals.printable_ratio >= self._settings.pymupdf_min_printable_ratio
            and text_signals.replacement_character_ratio <= self._settings.pymupdf_max_replacement_ratio
            and total_image_coverage <= self._settings.pymupdf_max_image_coverage
            and layout_complexity <= self._settings.pymupdf_max_layout_complexity
            and not probable_complex_table
            and not probable_scan
        )

        routing_hints: list[str] = []
        if probable_scan:
            routing_hints.append("probable_scan")
        if use_pymupdf:
            routing_hints.append("pymupdf_fast_path")
        if probable_complex_table:
            routing_hints.append("probable_complex_table")

        return PageInspection(
            page=page_number,
            width=page.rect.width,
            height=page.rect.height,
            rotation=page.rotation,
            text=text_signals,
            images=image_signals,
            layout=layout_signals,
            probable_scan=probable_scan,
            probable_complex_table=probable_complex_table,
            use_pymupdf_fast_path=use_pymupdf,
            routing_hints=routing_hints,
            metadata={"sample_text": full_text[:2000]},
        )

    @staticmethod
    def _rect_area(bbox: tuple[float, float, float, float] | list[float] | None) -> float:
        if not bbox or len(bbox) != 4:
            return 0.0
        return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])

    @staticmethod
    def _estimate_table_candidates(text_blocks: list[dict]) -> int:
        candidates = 0
        for block in text_blocks:
            lines = block.get("lines", [])
            if len(lines) < 2:
                continue
            column_counts = []
            for line in lines:
                spans = line.get("spans", [])
                if len(spans) >= 3:
                    column_counts.append(len(spans))
            if len(column_counts) >= 2 and max(column_counts) - min(column_counts) <= 1:
                candidates += 1
        return candidates

    @staticmethod
    def _estimate_dpi(image_width: float, image_height: float, page_width: float) -> float | None:
        if image_width <= 0 or page_width <= 0:
            return None
        scale = image_width / page_width
        return round(72.0 * scale, 2)
