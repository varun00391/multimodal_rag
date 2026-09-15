from pydantic import BaseModel, Field

from app.models.common import RegionType
from app.models.element import ExtractedElement


class Region(BaseModel):
    id: str
    type: RegionType = RegionType.UNKNOWN
    page: int
    bbox: list[float]
    bbox_pdf: list[float] = Field(default_factory=list)
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    score: float = 1.0
    source: str = "layout"
    native_object_ids: list[str] = Field(default_factory=list)
    element: ExtractedElement | None = None
    extra: dict = Field(default_factory=dict)
