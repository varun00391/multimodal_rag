from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from rag_shared.core.deps import CurrentUser, get_current_user, require_upload_permission
from rag_shared.core.errors import AppError
from rag_shared.db.session import get_db
from rag_shared.models.enums import IngestionJobStatus
from rag_shared.schemas.api import IngestionJobResponse
from rag_shared.services.documents import assert_document_access, get_document, get_ingestion_job
from rag_shared.services.ingestion_worker import schedule_ingestion_job

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _job_response(job) -> IngestionJobResponse:
    return IngestionJobResponse(
        job_id=job.id,
        document_id=job.document_id,
        status=job.status.value,
        progress=job.progress,
        current_step=job.current_step,
    )


async def _queue_ingestion(document, job, db: AsyncSession) -> IngestionJobResponse:
    if job.status in {
        IngestionJobStatus.EXTRACTING,
        IngestionJobStatus.CHUNKING,
        IngestionJobStatus.EMBEDDING,
        IngestionJobStatus.INDEXING,
    }:
        raise AppError("INGESTION_IN_PROGRESS", "Ingestion is already running.", status_code=409)

    if job.status == IngestionJobStatus.COMPLETED:
        return _job_response(job)

    job.status = IngestionJobStatus.QUEUED
    job.progress = 0
    job.current_step = "Queued for ingestion"
    job.error_message = None
    await db.commit()
    await db.refresh(job)

    scheduled = await schedule_ingestion_job(
        job_id=job.id,
        document_id=document.id,
        storage_path=document.storage_path,
        department_id=document.department_id,
        owner_user_id=document.owner_user_id,
    )
    if not scheduled:
        raise AppError("INGESTION_IN_PROGRESS", "Ingestion is already running.", status_code=409)
    return _job_response(job)


@router.post("/{document_id}/start", response_model=IngestionJobResponse)
async def start_ingestion(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_upload_permission),
) -> IngestionJobResponse:
    document = await get_document(db, document_id)
    assert_document_access(current, document)

    if not document.ingestion_jobs:
        raise AppError("INGESTION_FAILED", "No ingestion job exists for this document.", status_code=404)

    job = document.ingestion_jobs[-1]
    return await _queue_ingestion(document, job, db)


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> IngestionJobResponse:
    job = await get_ingestion_job(db, job_id)
    assert_document_access(current, job.document)
    return _job_response(job)


@router.post("/jobs/{job_id}/retry", response_model=IngestionJobResponse)
async def retry_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_upload_permission),
) -> IngestionJobResponse:
    job = await get_ingestion_job(db, job_id)
    assert_document_access(current, job.document)
    if job.status not in {IngestionJobStatus.FAILED}:
        raise AppError("INGESTION_IN_PROGRESS", "Only failed jobs can be retried.", status_code=409)

    job.status = IngestionJobStatus.QUEUED
    job.progress = 0
    job.current_step = "Retry queued"
    job.error_message = None
    return await _queue_ingestion(job.document, job, db)
