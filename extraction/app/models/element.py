from pydantic import BaseModel, Field

from app.models.common import RegionType
from app.models.provenance import Provenance
from app.models.validation import ValidationResult


class NativeObject(BaseModel):
    id: str
    type: str
    page: int
    bbox: list[float]
    bbox_pdf: list[float] = Field(default_factory=list)
    content: str | dict | list | None = None
    source: str = "pymupdf"
    extra: dict = Field(default_factory=dict)


class ExtractedElement(BaseModel):
    id: str
    type: RegionType | str
    page: int
    bbox: list[float]
    bbox_pdf: list[float] = Field(default_factory=list)
    reading_order: int | None = None
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    content: dict = Field(default_factory=dict)
    provenance: Provenance = Field(default_factory=Provenance)
    validation: ValidationResult = Field(default_factory=ValidationResult)
    assets: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
