from __future__ import annotations

import time

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.orchestration.pipeline import ExtractionPipeline

logger = get_logger(__name__)


def run_job(document_id: str, job_id: str) -> None:
    configure_logging()
    logger.info("Starting extraction job %s for document %s", job_id, document_id)
    ExtractionPipeline().run(document_id, job_id)
    logger.info("Finished extraction job %s", job_id)


def schedule_inline(background_tasks: BackgroundTasks, document_id: str, job_id: str) -> None:
    background_tasks.add_task(run_job, document_id, job_id)


def run_forever() -> None:
    configure_logging()
    settings = get_settings()
    from app.db.repository import get_repository

    repo = get_repository()
    logger.info("Extraction worker polling every %ss", settings.worker_poll_seconds)
    while True:
        job = repo.claim_next_queued()
        if job is None:
            time.sleep(settings.worker_poll_seconds)
            continue
        try:
            run_job(job.document_id, job.id)
        except Exception:
            logger.exception("Worker failed on job %s", job.id)


if __name__ == "__main__":
    run_forever()
