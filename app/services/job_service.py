from datetime import datetime, timezone
from uuid import uuid4

from app.errors import BenchmarkNotEnabledError, JobNotFoundError
from app.models.jobs import (
    ExtractionPolicy,
    JobCreateResponse,
    JobRecord,
    JobStatus,
    JobStatusResponse,
)
from app.storage.jobs import JobStore


class JobService:
    def __init__(self, job_store: JobStore) -> None:
        self._job_store = job_store

    async def create_job(
        self,
        *,
        document_id: str,
        original_filename: str | None,
        source_path: str,
        workspace_path: str,
        sha256: str,
        page_count: int,
        policy: ExtractionPolicy,
    ) -> JobCreateResponse:
        now = datetime.now(timezone.utc)
        job = JobRecord(
            job_id=f"job-{uuid4()}",
            document_id=document_id,
            status=JobStatus.QUEUED,
            original_filename=original_filename,
            source_path=source_path,
            workspace_path=workspace_path,
            sha256=sha256,
            page_count=page_count,
            policy=policy,
            created_at=now,
            updated_at=now,
        )
        await self._job_store.create(job)
        return JobCreateResponse(job_id=job.job_id, status=job.status)

    async def get_job(self, job_id: str) -> JobStatusResponse:
        job = await self._require_job(job_id)
        return JobStatusResponse(
            job_id=job.job_id,
            document_id=job.document_id,
            status=job.status,
            page_count=job.page_count,
            sha256=job.sha256,
            policy=job.policy,
            error_code=job.error_code,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    async def mark_status(self, job_id: str, status: JobStatus) -> JobRecord:
        job = await self._job_store.update_status(job_id, status)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    async def mark_failed(
        self,
        job_id: str,
        *,
        error_code: str,
        error_message: str,
    ) -> JobRecord:
        job = await self._job_store.update_status(
            job_id,
            JobStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
        )
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    async def require_job_record(self, job_id: str) -> JobRecord:
        return await self._require_job(job_id)

    @staticmethod
    def validate_policy_options(
        policy: ExtractionPolicy,
        *,
        benchmark_enabled: bool,
        default_allow_managed_apis: bool,
    ) -> ExtractionPolicy:
        if policy.force_extractor or policy.compare_extractors:
            if not benchmark_enabled:
                raise BenchmarkNotEnabledError()

        if policy.page_start is not None and policy.page_end is not None:
            if policy.page_start > policy.page_end:
                from app.errors import InputValidationError

                raise InputValidationError(
                    "INVALID_PAGE_RANGE",
                    "page_start must be less than or equal to page_end.",
                )

        return ExtractionPolicy(
            allow_managed_apis=policy.allow_managed_apis and default_allow_managed_apis,
            visual_understanding=policy.visual_understanding,
            page_start=policy.page_start,
            page_end=policy.page_end,
            force_extractor=policy.force_extractor,
            compare_extractors=policy.compare_extractors,
        )

    async def _require_job(self, job_id: str) -> JobRecord:
        job = await self._job_store.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job
