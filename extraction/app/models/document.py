from pydantic import BaseModel, Field

from app.models.common import JobStatus
from app.models.page import PageModel, PageProfile


class DocumentProfile(BaseModel):
    page_count: int = 0
    pdf_version: str | None = None
    encrypted: bool = False
    is_probably_scanned: bool = False
    is_hybrid: bool = False
    is_born_digital: bool = True
    native_text_chars: int = 0
    image_count: int = 0
    vector_count: int = 0
    fonts: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    pages: list[PageProfile] = Field(default_factory=list)


class Relationship(BaseModel):
    source_id: str
    target_id: str
    type: str
    extra: dict = Field(default_factory=dict)


class AssetRef(BaseModel):
    id: str
    kind: str
    path: str
    page: int | None = None
    region_id: str | None = None


class CanonicalDocument(BaseModel):
    document: dict = Field(default_factory=dict)
    pages: list[PageModel] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    assets: list[AssetRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    profile: DocumentProfile | None = None


class DocumentRecord(BaseModel):
    id: str
    filename: str
    content_type: str = "application/pdf"
    sha256: str
    size_bytes: int
    page_count: int | None = None
    status: JobStatus = JobStatus.UPLOADED
    job_id: str
    created_at: str
    updated_at: str
    error_code: str | None = None
    warnings: list[str] = Field(default_factory=list)


class JobRecord(BaseModel):
    id: str
    document_id: str
    status: JobStatus = JobStatus.QUEUED
    current_step: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None


class ReviewItem(BaseModel):
    id: str
    document_id: str
    region_id: str
    page_number: int
    status: str = "PENDING"
    reason: str
    bbox: list[float] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)
    confidence: float | None = None
    decision: dict | None = None
    created_at: str
    updated_at: str
