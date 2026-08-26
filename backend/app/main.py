from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.health import router as health_router
from app.api.internal import router as internal_router
from app.api.v1.router import api_router
from app.config import get_settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.middleware import RequestContextMiddleware
from app.db.init_db import init_database

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("starting_app", app_name=settings.app_name, env=settings.app_env)
    if not settings.super_admin_email:
        raise RuntimeError("SUPER_ADMIN_EMAIL must be set.")
    await init_database()
    yield
    logger.info("shutting_down_app")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        https_only=settings.app_env == "production",
        same_site="lax",
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(internal_router)

    return app


app = create_app()
