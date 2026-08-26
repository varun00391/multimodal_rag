from __future__ import annotations

import time

import httpx
import structlog
from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware

from rag_shared.app_factory import create_service_app
from rag_shared.config import get_settings
from rag_shared.core.errors import AppError
from rag_shared.db.session import SessionLocal
from rag_shared.models.entities import User
from rag_shared.models.enums import UserStatus
from rag_shared.openapi_aggregation import attach_aggregated_openapi, prewarm_aggregated_openapi
from rag_shared.routers.auth import router as auth_router
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = structlog.get_logger(__name__)

# Auth routes are mounted on the gateway (not proxied) so OAuth session state and
# the browser session cookie both live on the same service. Proxying breaks the
# OAuth CSRF state check with duplicate SessionMiddleware instances.
# Longest-prefix matches must win (e.g. /api/v1/users/me before /api/v1/users).
ROUTE_MAP: list[tuple[str, str]] = [
    ("/api/v1/departments", "user_management_service_url"),
    ("/api/v1/admins", "user_management_service_url"),
    ("/api/v1/users/me", "query_service_url"),
    ("/api/v1/users", "user_management_service_url"),
    ("/api/v1/documents", "documents_service_url"),
    ("/api/v1/ingestion", "ingestion_service_url"),
    ("/api/v1/retrieval", "retrieval_service_url"),
    ("/api/v1/query", "query_service_url"),
    ("/api/v1/dashboard", "dashboard_service_url"),
    ("/api/v1/audit-logs", "dashboard_service_url"),
]


def _resolve_target(path: str, settings) -> str | None:
    matches = [(prefix, setting_name) for prefix, setting_name in ROUTE_MAP if path.startswith(prefix)]
    if not matches:
        return None
    prefix, setting_name = max(matches, key=lambda item: len(item[0]))
    base = getattr(settings, setting_name)
    return f"{base.rstrip('/')}{path}"


async def _load_user_headers(request: Request) -> dict[str, str]:
    user_id = request.session.get("user_id")
    if not user_id:
        return {}
    async with SessionLocal() as db:
        result = await db.execute(
            select(User)
            .options(selectinload(User.department_assignments))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user or user.status != UserStatus.ACTIVE:
            return {}
        department_ids = ",".join(a.department_id for a in user.department_assignments)
        return {
            "X-User-Id": user.id,
            "X-User-Role": user.role.value,
            "X-Department-Ids": department_ids,
        }


def _forward_headers(request: Request, extra: dict[str, str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    if request.headers.get("cookie"):
        headers["cookie"] = request.headers["cookie"]
    if request.headers.get("content-type"):
        headers["content-type"] = request.headers["content-type"]
    if request.headers.get("x-request-id"):
        headers["x-request-id"] = request.headers["x-request-id"]
    headers.update(extra)
    return headers


app = create_service_app(
    service_name="gateway",
    routers=[auth_router],
    init_db=True,
    enable_session=True,
    lifespan_hook=prewarm_aggregated_openapi,
)
attach_aggregated_openapi(app)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_api(path: str, request: Request) -> Response:
    settings = get_settings()
    full_path = f"/api/v1/{path}"
    target = _resolve_target(full_path, settings)
    if not target:
        raise AppError("NOT_FOUND", f"No upstream service for {full_path}", status_code=404)

    user_headers = await _load_user_headers(request)
    body = await request.body()
    headers = _forward_headers(request, user_headers)
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        "gateway_proxy_start",
        method=request.method,
        path=full_path,
        upstream=target,
        user_id=user_headers.get("X-User-Id"),
        request_id=request_id,
    )

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=600.0) as client:
        upstream = await client.request(
            request.method,
            target,
            params=request.query_params,
            content=body,
            headers=headers,
        )
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    if upstream.status_code >= 400:
        logger.warning(
            "gateway_proxy_upstream_error",
            method=request.method,
            path=full_path,
            upstream=target,
            status_code=upstream.status_code,
            response_body=upstream.text[:1000],
            duration_ms=duration_ms,
            request_id=request_id,
        )
    else:
        logger.info(
            "gateway_proxy_complete",
            method=request.method,
            path=full_path,
            upstream=target,
            status_code=upstream.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in {"content-encoding", "transfer-encoding", "connection"}
    }
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)
