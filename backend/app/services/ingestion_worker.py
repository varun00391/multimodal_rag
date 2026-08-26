from __future__ import annotations

import asyncio
import logging

from app.config import Settings, get_settings
from app.db.sync_session import persist_document_elements, update_document_status, update_ingestion_job
from app.models.enums import DocumentStatus, IngestionJobStatus
from app.services.ingestion_pipeline import (
    map_job_status_to_document_status,
    run_ingestion_sync,
)

LOGGER = logging.getLogger(__name__)

_running_jobs: set[str] = set()


def _execute_ingestion_job(
    *,
    job_id: str,
    document_id: str,
    storage_path: str,
    app_settings: Settings,
) -> None:
    def on_progress(status: IngestionJobStatus, progress: int, step: str) -> None:
        update_ingestion_job(
            job_id,
            status=status,
            progress=progress,
            current_step=step,
        )
        update_document_status(document_id, map_job_status_to_document_status(status))

    try:
        on_progress(IngestionJobStatus.QUEUED, 0, "Queued for ingestion")
        result = run_ingestion_sync(
            document_id=document_id,
            storage_path=storage_path,
            app_settings=app_settings,
            on_progress=on_progress,
        )
        persist_document_elements(document_id, result["parents"])
        update_ingestion_job(
            job_id,
            status=IngestionJobStatus.COMPLETED,
            progress=100,
            current_step="Ingestion complete",
            error_message=None,
        )
        update_document_status(document_id, DocumentStatus.READY)
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


async def schedule_ingestion_job(
    *,
    job_id: str,
    document_id: str,
    storage_path: str,
) -> bool:
    if job_id in _running_jobs:
        return False

    _running_jobs.add(job_id)
    settings = get_settings()

    async def _runner() -> None:
        try:
            await asyncio.to_thread(
                _execute_ingestion_job,
                job_id=job_id,
                document_id=document_id,
                storage_path=storage_path,
                app_settings=settings,
            )
        except Exception:
            pass
        finally:
            _running_jobs.discard(job_id)

    asyncio.create_task(_runner())
    return True
