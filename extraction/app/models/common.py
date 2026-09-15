from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

BBox = Annotated[list[float], Field(min_length=4, max_length=4)]


class JobStatus(str, Enum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROFILING = "PROFILING"
    REGION_DETECTION = "REGION_DETECTION"
    EXTRACTING = "EXTRACTING"
    VALIDATING = "VALIDATING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    RECONSTRUCTING = "RECONSTRUCTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    CANCELLED = "CANCELLED"


class RegionType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    COMPLEX_TABLE = "complex_table"
    IMAGE = "image"
    FIGURE = "figure"
    CHART = "chart"
    DIAGRAM = "diagram"
    EQUATION = "equation"
    FORM = "form"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"
    SIGNATURE = "signature"
    UNKNOWN = "unknown"


class ValidationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    AGREED = "AGREED"
    CONFLICT = "CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNREADABLE = "UNREADABLE"
    PARTIAL = "PARTIAL"
    PENDING_REVIEW = "PENDING_REVIEW"
    REVIEWED = "REVIEWED"


class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"


class PointBBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

    def as_list(self) -> list[float]:
        return [self.x0, self.y0, self.x1, self.y1]

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    def contains_point(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (
            self.x0 - margin <= x <= self.x1 + margin
            and self.y0 - margin <= y <= self.y1 + margin
        )


def bbox_from_seq(seq: list[float] | tuple[float, ...]) -> PointBBox:
    x0, y0, x1, y1 = (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    return PointBBox(x0=min(x0, x1), y0=min(y0, y1), x1=max(x0, x1), y1=max(y0, y1))


def pdf_bbox_to_px(bbox: list[float], dpi: int) -> list[float]:
    scale = dpi / 72.0
    return [round(v * scale, 2) for v in bbox]


def intersection_area(a: PointBBox, b: PointBBox) -> float:
    x0 = max(a.x0, b.x0)
    y0 = max(a.y0, b.y0)
    x1 = min(a.x1, b.x1)
    y1 = min(a.y1, b.y1)
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def iou(a: PointBBox, b: PointBBox) -> float:
    inter = intersection_area(a, b)
    if inter <= 0:
        return 0.0
    union = a.area + b.area - inter
    return inter / union if union else 0.0


def center(bbox: PointBBox) -> tuple[float, float]:
    return ((bbox.x0 + bbox.x1) / 2.0, (bbox.y0 + bbox.y1) / 2.0)
