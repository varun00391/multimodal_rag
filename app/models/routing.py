from typing import Any

from pydantic import BaseModel, Field


class ExtractionTask(BaseModel):
    document_id: str | None = None
    page: int
    kind: str
    extractor: str
    profile: str | None = None
    region: list[float] | None = None
    required: bool = False
    options_hash: str | None = None
    privacy_mode: str | None = None


class PagePlan(BaseModel):
    page: int
    primary_route: str | None = None
    tasks: list[ExtractionTask] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ExtractionGroup(BaseModel):
    group_id: str
    document_id: str
    extractor: str
    profile: str | None = None
    kind: str
    pages: list[int] = Field(default_factory=list)
    options_hash: str | None = None
    privacy_mode: str | None = None
    context_pages: list[int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tasks: list[ExtractionTask] = Field(default_factory=list)
