from pydantic import BaseModel, Field


class ProvenanceSource(BaseModel):
    engine: str
    model_version: str = ""
    extra: dict = Field(default_factory=dict)


class Provenance(BaseModel):
    document_id: str = ""
    page: int | None = None
    bbox: list[float] = Field(default_factory=list)
    sources: list[ProvenanceSource] = Field(default_factory=list)
