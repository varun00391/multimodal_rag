from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    QUEUED = "queued"
    VALIDATING_INPUT = "validating_input"
    INSPECTING = "inspecting"
    PLANNING = "planning"
    EXTRACTING = "extracting"
    VALIDATING_OUTPUT = "validating_output"
    RETRYING = "retrying"
    MERGING = "merging"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


TERMINAL_JOB_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.COMPLETED_WITH_WARNINGS,
    JobStatus.FAILED,
}


_UNSET_FORCE_EXTRACTOR = {"", "null", "none", "undefined"}


class ExtractionPolicy(BaseModel):
    allow_managed_apis: bool = True
    visual_understanding: bool = False
    page_start: int | None = None
    page_end: int | None = None
    force_extractor: str | None = None
    compare_extractors: bool = False

    @field_validator("force_extractor", mode="before")
    @classmethod
    def normalize_force_extractor(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in _UNSET_FORCE_EXTRACTOR:
            return None
        if isinstance(value, str):
            return value.strip()
        return value


class JobRecord(BaseModel):
    job_id: str
    document_id: str
    status: JobStatus
    original_filename: str | None = None
    source_path: str
    workspace_path: str
    sha256: str
    page_count: int
    policy: ExtractionPolicy
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    cache_hit: bool = False
    document_path: str | None = None
    report_path: str | None = None
    created_at: datetime
    updated_at: datetime


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    document_id: str
    status: JobStatus
    original_filename: str | None = None
    page_count: int
    sha256: str
    policy: ExtractionPolicy
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    cache_hit: bool = False
    created_at: datetime
    updated_at: datetime


class JobListItem(BaseModel):
    job_id: str
    original_filename: str | None = None
    status: JobStatus
    page_count: int
    duration_ms: int | None = None
    cache_hit: bool = False
    created_at: datetime
    force_extractor: str | None = None


class ValidatedPdfInput(BaseModel):
    document_id: str
    sha256: str
    page_count: int
    size_bytes: int
    workspace_path: str
    source_path: str
    page_range: tuple[int, int] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
