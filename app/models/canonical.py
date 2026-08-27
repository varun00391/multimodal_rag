from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ElementType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    PICTURE = "picture"
    CHART = "chart"
    DIAGRAM = "diagram"
    FORMULA = "formula"
    CODE = "code"
    KEY_VALUE = "key_value"
    FORM_FIELD = "form_field"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    PAGE_NUMBER = "page_number"
    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    left: float
    top: float
    right: float
    bottom: float
    coordinate_origin: str = "top-left"
    unit: str = "pdf-point"

    @property
    def width(self) -> float:
        return max(0.0, self.right - self.left)

    @property
    def height(self) -> float:
        return max(0.0, self.bottom - self.top)

    @property
    def area(self) -> float:
        return self.width * self.height


class ExtractorProvenance(BaseModel):
    name: str
    version: str | None = None
    adapter_version: str | None = None
    profile: str | None = None
    model: str | None = None
    prompt_version: int | None = None


class ElementProvenance(BaseModel):
    source_page: int
    source_coordinate_system: str = "pdf-points-top-left"
    routing_policy_version: str | None = None
    attempt: int = 1


class CanonicalElement(BaseModel):
    element_id: str
    type: ElementType
    page: int
    reading_order: int
    text: str | None = None
    markdown: str | None = None
    html: str | None = None
    bbox: BoundingBox | None = None
    asset: str | None = None
    confidence: float | None = None
    extractor: ExtractorProvenance | None = None
    provenance: ElementProvenance | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionError(BaseModel):
    code: str
    message: str
    page: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ExtractionAttempt(BaseModel):
    attempt: int
    extractor: str
    profile: str | None = None
    status: str
    duration_ms: int | None = None
    element_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[ExtractionError] = Field(default_factory=list)


class CanonicalPage(BaseModel):
    page: int
    width: float
    height: float
    rotation: int = 0
    primary_route: str | None = None
    routing_confidence: float | None = None
    validation_confidence: float | None = None
    overall_confidence: float | None = None
    routing_reasons: list[str] = Field(default_factory=list)
    extraction_routes: list[str] = Field(default_factory=list)
    elements: list[CanonicalElement] = Field(default_factory=list)
    attempts: list[ExtractionAttempt] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[ExtractionError] = Field(default_factory=list)


class DocumentSource(BaseModel):
    filename: str | None = None
    media_type: str = "application/pdf"
    sha256: str
    size_bytes: int


class DocumentSummary(BaseModel):
    element_counts: dict[str, int] = Field(default_factory=dict)
    route_counts: dict[str, int] = Field(default_factory=dict)
    failed_pages: list[int] = Field(default_factory=list)
    scanned_pages: list[int] = Field(default_factory=list)
    duration_ms: int = 0
    estimated_cost_usd: float = 0.0


class CanonicalDocument(BaseModel):
    schema_version: str
    document_id: str
    source: DocumentSource
    status: str
    page_count: int
    pages: list[CanonicalPage] = Field(default_factory=list)
    summary: DocumentSummary = Field(default_factory=DocumentSummary)


class CanonicalExtractionResult(BaseModel):
    pages: list[CanonicalPage]
    attempts: list[ExtractionAttempt] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[ExtractionError] = Field(default_factory=list)
    duration_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
