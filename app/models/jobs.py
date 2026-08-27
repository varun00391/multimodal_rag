from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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


class ExtractionPolicy(BaseModel):
    allow_managed_apis: bool = True
    visual_understanding: bool = False
    page_start: int | None = None
    page_end: int | None = None
    force_extractor: str | None = None
    compare_extractors: bool = False


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
    created_at: datetime
    updated_at: datetime


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    document_id: str
    status: JobStatus
    page_count: int
    sha256: str
    policy: ExtractionPolicy
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ValidatedPdfInput(BaseModel):
    document_id: str
    sha256: str
    page_count: int
    size_bytes: int
    workspace_path: str
    source_path: str
    page_range: tuple[int, int] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
