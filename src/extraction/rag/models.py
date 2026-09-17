from __future__ import annotations

from pydantic import BaseModel, Field


class ChildChunk(BaseModel):
    child_id: str
    parent_id: str
    parent_type: str
    parent_text: str
    child_text: str
    embed_text: str
    element_type: str
    modality: str
    unit_type: str
    unit_index: int
    element_ids: list[str] = Field(default_factory=list)
    asset_path: str | None = None
    t_start: float | None = None
    t_end: float | None = None
    filename: str
    media_type: str
    document_id: str


class ChildHit(BaseModel):
    child_id: str
    parent_id: str
    parent_type: str
    parent_text: str
    child_text: str
    score: float
    filename: str
    unit_type: str
    unit_index: int
    element_type: str
    modality: str
    asset_path: str | None = None
    t_start: float | None = None
    t_end: float | None = None
    document_id: str
    dense_score: float | None = None
    bm25_hit: bool = False


class RetrievedParent(BaseModel):
    parent_id: str
    parent_type: str
    parent_text: str
    filename: str
    unit_type: str
    unit_index: int
    score: float
    children: list[ChildHit] = Field(default_factory=list)
