from typing import Any

from pydantic import BaseModel, Field


class TextSignals(BaseModel):
    character_count: int = 0
    word_count: int = 0
    block_count: int = 0
    line_count: int = 0
    span_count: int = 0
    printable_ratio: float = 0.0
    replacement_character_ratio: float = 0.0
    control_character_ratio: float = 0.0
    text_coverage: float = 0.0
    duplicate_text_ratio: float = 0.0
    overlapping_text_ratio: float = 0.0
    valid_bbox_ratio: float = 0.0
    font_count: int = 0
    font_size_distribution: dict[str, int] = Field(default_factory=dict)
    suspicious_hidden_ocr: bool = False
    average_word_length: float = 0.0


class ImageSignals(BaseModel):
    image_count: int = 0
    largest_image_coverage: float = 0.0
    total_image_coverage: float = 0.0
    near_full_page_raster: bool = False
    max_image_width: float = 0.0
    max_image_height: float = 0.0
    effective_resolution_dpi: float | None = None
    native_text_despite_image_coverage: bool = False


class LayoutSignals(BaseModel):
    probable_columns: int = 1
    irregular_block_order: float = 0.0
    vector_drawing_count: int = 0
    table_candidate_count: int = 0
    figure_candidate_count: int = 0
    rotated_text: bool = False
    has_header_region: bool = False
    has_footer_region: bool = False
    formula_like_regions: int = 0
    code_like_regions: int = 0
    layout_complexity: float = 0.0


class ContinuitySignals(BaseModel):
    table_continues_to_next: bool = False
    repeated_table_header_on_next: bool = False
    incomplete_sentence: bool = False
    continuing_list: bool = False
    figure_caption_split: bool = False
    continuing_columns_or_fonts: bool = False


class PageInspection(BaseModel):
    page: int
    width: float
    height: float
    rotation: int = 0
    text: TextSignals = Field(default_factory=TextSignals)
    images: ImageSignals = Field(default_factory=ImageSignals)
    layout: LayoutSignals = Field(default_factory=LayoutSignals)
    continuity: ContinuitySignals = Field(default_factory=ContinuitySignals)
    probable_scan: bool = False
    probable_complex_table: bool = False
    use_pymupdf_fast_path: bool = False
    routing_hints: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentInspection(BaseModel):
    schema_version: str
    document_id: str
    page_count: int
    pages: list[PageInspection] = Field(default_factory=list)
    continuity: list[ContinuitySignals] = Field(default_factory=list)
