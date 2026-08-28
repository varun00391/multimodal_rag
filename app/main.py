from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.docling_profiles import apply_docling_artifacts_path
from app.api.dependencies import get_docling_adapter, get_job_store
from app.api.routes import router
from app.config import get_settings
from app.errors import register_exception_handlers
from app.observability.logging import configure_json_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.extraction_log_json:
        configure_json_logging()
    apply_docling_artifacts_path(settings)
    job_store = get_job_store()
    await job_store.initialize()
    if settings.docling_warm_on_startup:
        get_docling_adapter().warm_profiles()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PDF Extraction API",
        version=settings.extraction_schema_version,
        lifespan=lifespan,
    )
    origins = settings.cors_origin_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
