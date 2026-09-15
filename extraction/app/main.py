from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_documents import router as documents_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_review import router as review_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.repository import get_repository

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_repository()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Multimodal PDF extraction API (region-level pipeline).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(jobs_router)
app.include_router(review_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
