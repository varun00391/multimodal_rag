from pydantic import BaseModel, Field

from app.models.element import NativeObject
from app.models.region import Region


class PageProfile(BaseModel):
    page_number: int
    width: float
    height: float
    width_px: int = 0
    height_px: int = 0
    rotation: int = 0
    native_text_chars: int = 0
    image_count: int = 0
    vector_count: int = 0
    has_ocr_layer: bool = False
    is_probably_scanned: bool = False
    font_count: int = 0
    annotation_count: int = 0
    link_count: int = 0
    mediabox: list[float] = Field(default_factory=list)


class PageModel(BaseModel):
    page_number: int
    width: float
    height: float
    width_px: int = 0
    height_px: int = 0
    dpi: int = 200
    image_path: str | None = None
    profile: PageProfile | None = None
    native_objects: list[NativeObject] = Field(default_factory=list)
    regions: list[Region] = Field(default_factory=list)
