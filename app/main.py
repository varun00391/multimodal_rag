from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dependencies import get_job_store
from app.api.routes import router
from app.config import get_settings
from app.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    job_store = get_job_store()
    await job_store.initialize()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PDF Extraction API",
        version=settings.extraction_schema_version,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
