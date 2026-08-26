from __future__ import annotations

import asyncio
import logging

import httpx

from rag_shared.config import Settings, get_settings
from rag_shared.db.sync_session import persist_document_elements, update_document_status, update_ingestion_job
from rag_shared.models.enums import DocumentStatus, IngestionJobStatus
from rag_shared.schemas.internal import (
    ChunkingRequest,
    ExtractionRequest,
    IndexUpsertRequest,
    IngestionStartRequest,
    JobEventPayload,
)
from rag_shared.services.ingestion_status import map_job_status_to_document_status
from rag_shared.workspace import prepare_document_pdf

LOGGER = logging.getLogger(__name__)
_running_jobs: set[str] = set()


async def _notify_job_event(settings: Settings, event: JobEventPayload) -> None:
    url = f"{settings.notifications_service_url}/internal/v1/notifications/job-event"
    headers = {"X-Internal-Token": settings.internal_service_token}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=event.model_dump(), headers=headers)
    except Exception:
        LOGGER.debug("notification_dispatch_skipped", job_id=event.job_id)


def _post_sync(settings: Settings, url: str, payload: dict) -> dict:
    headers = {"X-Internal-Token": settings.internal_service_token}
    with httpx.Client(timeout=600.0) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def _run_pipeline_sync(
    *,
    job_id: str,
    document_id: str,
    storage_path: str,
    department_id: str | None,
    owner_user_id: str | None,
    settings: Settings,
) -> None:
    def progress(status: IngestionJobStatus, pct: int, step: str) -> None:
        update_ingestion_job(job_id, status=status, progress=pct, current_step=step)
        update_document_status(document_id, map_job_status_to_document_status(status))

    try:
        progress(IngestionJobStatus.QUEUED, 0, "Queued for ingestion")
        progress(IngestionJobStatus.EXTRACTING, 5, "Preparing document workspace")
        _, pdf_path = prepare_document_pdf(document_id, storage_path, settings.upload_dir)

        progress(IngestionJobStatus.EXTRACTING, 15, "Extracting PDF with Docling")
        extraction = _post_sync(
            settings,
            f"{settings.extraction_service_url}/internal/v1/extraction/extract",
            ExtractionRequest(
                document_id=document_id,
                storage_path=str(pdf_path),
                upload_dir=settings.upload_dir,
            ).model_dump(),
        )

        progress(IngestionJobStatus.CHUNKING, 40, "Chunking and enriching document")
        chunking = _post_sync(
            settings,
            f"{settings.chunking_service_url}/internal/v1/indexing/chunk",
            ChunkingRequest(
                document_id=document_id,
                document_json=extraction["document_json"],
                rag_path=extraction["rag_path"],
            ).model_dump(),
        )

        progress(IngestionJobStatus.EMBEDDING, 75, "Generating embeddings")
        progress(IngestionJobStatus.INDEXING, 90, "Indexing vectors in Qdrant")
        index_result = _post_sync(
            settings,
            f"{settings.chunking_service_url}/internal/v1/indexing/upsert",
            IndexUpsertRequest(
                document_id=document_id,
                rag_path=chunking["rag_path"],
                department_id=department_id,
                owner_user_id=owner_user_id,
            ).model_dump(),
        )

        from rag.io_utils import read_jsonl
        from pathlib import Path

        parents = read_jsonl(Path(chunking["rag_path"]) / "parents.jsonl")
        persist_document_elements(document_id, parents)

        progress(IngestionJobStatus.COMPLETED, 100, "Ingestion complete")
        update_ingestion_job(
            job_id,
            status=IngestionJobStatus.COMPLETED,
            progress=100,
            current_step="Ingestion complete",
            error_message=None,
        )
        update_document_status(document_id, DocumentStatus.READY)
        LOGGER.info(
            "ingestion_completed",
            job_id=job_id,
            document_id=document_id,
            indexed_count=index_result.get("indexed_count"),
        )
    except Exception as error:
        LOGGER.exception("ingestion_failed", job_id=job_id, document_id=document_id)
        update_ingestion_job(
            job_id,
            status=IngestionJobStatus.FAILED,
            progress=0,
            current_step="Ingestion failed",
            error_message=str(error),
        )
        update_document_status(document_id, DocumentStatus.FAILED_INDEXING)
        raise


async def schedule_ingestion_job(request: IngestionStartRequest) -> bool:
    if request.job_id in _running_jobs:
        return False

    _running_jobs.add(request.job_id)
    settings = get_settings()

    async def _runner() -> None:
        try:
            await asyncio.to_thread(
                _run_pipeline_sync,
                job_id=request.job_id,
                document_id=request.document_id,
                storage_path=request.storage_path,
                department_id=request.department_id,
                owner_user_id=request.owner_user_id,
                settings=settings,
            )
            await _notify_job_event(
                settings,
                JobEventPayload(
                    job_id=request.job_id,
                    document_id=request.document_id,
                    status=IngestionJobStatus.COMPLETED.value,
                    progress=100,
                    current_step="Ingestion complete",
                ),
            )
        except Exception as error:
            await _notify_job_event(
                settings,
                JobEventPayload(
                    job_id=request.job_id,
                    document_id=request.document_id,
                    status=IngestionJobStatus.FAILED.value,
                    progress=0,
                    current_step="Ingestion failed",
                    error_message=str(error),
                ),
            )
        finally:
            _running_jobs.discard(request.job_id)

    asyncio.create_task(_runner())
    return True
