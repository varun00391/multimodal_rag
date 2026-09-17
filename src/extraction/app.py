from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from extraction.api.routes import router
from extraction.jobs.store import JobStore
from extraction.jobs.worker import run_worker
from extraction.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    store = JobStore(settings.jobs_db_path)
    task = asyncio.create_task(run_worker(settings, store))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Multimodal extraction RAG", version="0.2.0", lifespan=lifespan)
app.include_router(router)
