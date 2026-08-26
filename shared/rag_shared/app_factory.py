from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager

import structlog
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from starlette.middleware.sessions import SessionMiddleware

from rag_shared.config import Settings, get_settings
from rag_shared.core.errors import AppError, app_error_handler, unhandled_error_handler
from rag_shared.core.middleware import RequestContextMiddleware
from rag_shared.db.init_db import init_database
from rag_shared.health import router as health_router

logger = structlog.get_logger(__name__)


def verify_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    settings = get_settings()
    if x_internal_token != settings.internal_service_token:
        raise HTTPException(status_code=403, detail="Invalid internal service token")


def create_service_app(
    *,
    service_name: str,
    routers: Sequence[APIRouter] = (),
    internal_routers: Sequence[APIRouter] = (),
    api_prefix: str | None = None,
    init_db: bool = False,
    enable_session: bool = False,
    lifespan_hook: Callable | None = None,
) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("starting_service", service=service_name, env=settings.app_env)
        if init_db:
            if not settings.super_admin_email and service_name in {"auth", "gateway"}:
                logger.warning("super_admin_email_not_set")
            await init_database()
        if lifespan_hook:
            async with lifespan_hook(app):
                yield
        else:
            yield
        logger.info("shutting_down_service", service=service_name)

    app = FastAPI(title=f"{settings.app_name} - {service_name}", version="0.2.0", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    if enable_session:
        app.add_middleware(
            SessionMiddleware,
            secret_key=settings.session_secret_key,
            https_only=settings.app_env == "production",
            same_site="lax",
        )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(health_router)

    prefix = api_prefix if api_prefix is not None else settings.api_prefix
    for router in routers:
        app.include_router(router, prefix=prefix)
    for router in internal_routers:
        app.include_router(router, prefix=settings.internal_prefix, dependencies=[Depends(verify_internal_token)])

    return app
