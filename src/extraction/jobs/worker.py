from __future__ import annotations

import asyncio
import logging

from extraction.errors import ExtractionError
from extraction.intake import document_dir
from extraction.jobs.store import JobStore
from extraction.pipeline import run_pipeline
from extraction.settings import Settings
from extraction.store import load_document

LOGGER = logging.getLogger(__name__)


async def run_worker(settings: Settings, store: JobStore) -> None:
    while True:
        job = await asyncio.to_thread(store.claim_next)
        if job is None:
            await asyncio.sleep(0.4)
            continue
        LOGGER.info("Running extraction job %s", job.job_id)
        try:
            workspace = document_dir(settings, job.document_id)
            original_dir = workspace / "original"
            files = list(original_dir.iterdir()) if original_dir.is_dir() else []
            if not files:
                raise ExtractionError("MISSING_ORIGINAL", "Original file is missing from workspace.")
            existing = load_document(workspace)
            if existing and existing.status in {"completed", "completed_with_warnings"}:
                store.complete(job.job_id)
                continue
            await asyncio.to_thread(
                run_pipeline,
                settings,
                files[0],
                job.filename,
                job.job_id,
            )
            store.complete(job.job_id)
        except ExtractionError as exc:
            LOGGER.warning("Job %s failed: %s", job.job_id, exc.message)
            store.fail(job.job_id, f"{exc.code}: {exc.message}")
        except Exception:
            LOGGER.exception("Job %s crashed", job.job_id)
            store.fail(job.job_id, "INTERNAL_ERROR: extraction worker crashed")
