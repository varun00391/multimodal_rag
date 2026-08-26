from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from rag_shared.config import Settings, get_settings

logger = structlog.get_logger(__name__)

# One OpenAPI document per upstream public API service (deduplicated by base URL).
OPENAPI_SERVICE_SOURCES: list[tuple[str, str]] = [
    ("user-management", "user_management_service_url"),
    ("documents", "documents_service_url"),
    ("ingestion-orchestrator", "ingestion_service_url"),
    ("retrieval", "retrieval_service_url"),
    ("query", "query_service_url"),
    ("dashboard", "dashboard_service_url"),
]

PROXY_PATH_FRAGMENT = "{path}"
UPSTREAM_EXCLUDED_PATHS = frozenset({"/health", "/ready", "/metrics"})


def _merge_dicts(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for key, value in incoming.items():
        if key not in base:
            base[key] = value
        elif isinstance(base[key], dict) and isinstance(value, dict):
            base[key].update(value)
        else:
            base[key] = value
    return base


def _merge_tags(base: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {tag["name"]: tag for tag in base if "name" in tag}
    for tag in incoming:
        name = tag.get("name")
        if name and name not in by_name:
            by_name[name] = tag
    return list(by_name.values())


def _strip_upstream_noise(document: dict[str, Any]) -> dict[str, Any]:
    paths = {
        path: operations
        for path, operations in document.get("paths", {}).items()
        if path not in UPSTREAM_EXCLUDED_PATHS and PROXY_PATH_FRAGMENT not in path
    }
    return {**document, "paths": paths}


def merge_openapi_documents(*documents: dict[str, Any]) -> dict[str, Any]:
    if not documents:
        return {}

    merged: dict[str, Any] = {
        "openapi": documents[0].get("openapi", "3.1.0"),
        "info": documents[0].get("info", {}),
        "paths": {},
        "components": {},
        "tags": [],
    }

    for document in documents:
        for path, operations in document.get("paths", {}).items():
            if path in merged["paths"]:
                logger.warning("openapi_path_collision", path=path)
            merged["paths"][path] = operations

        merged["components"] = _merge_dicts(merged.get("components", {}), document.get("components", {}))
        merged["tags"] = _merge_tags(merged.get("tags", []), document.get("tags", []))

    return merged


def _gateway_local_openapi(app: FastAPI, settings: Settings) -> dict[str, Any]:
    schema = get_openapi(
        title=settings.app_name,
        version="0.2.0",
        description=(
            "Unified API documentation for the Multimodal RAG microservices. "
            "All /api/v1/* requests are served through this gateway on port 8000."
        ),
        routes=app.routes,
    )
    schema["paths"] = {
        path: operations
        for path, operations in schema.get("paths", {}).items()
        if PROXY_PATH_FRAGMENT not in path
    }
    return schema


def fetch_service_openapi(
    service_name: str,
    base_url: str,
    *,
    client: httpx.Client,
) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}/openapi.json"
    try:
        response = client.get(url)
        response.raise_for_status()
        return _strip_upstream_noise(response.json())
    except Exception as exc:
        logger.warning("openapi_fetch_failed", service=service_name, url=url, error=str(exc))
        return None


def build_aggregated_openapi(app: FastAPI, settings: Settings | None = None) -> tuple[dict[str, Any], bool]:
    settings = settings or get_settings()
    documents = [_gateway_local_openapi(app, settings)]
    all_services_loaded = True

    with httpx.Client(timeout=10.0) as client:
        for service_name, setting_name in OPENAPI_SERVICE_SOURCES:
            base_url = getattr(settings, setting_name)
            schema = fetch_service_openapi(service_name, base_url, client=client)
            if schema:
                documents.append(schema)
            else:
                all_services_loaded = False

    merged = merge_openapi_documents(*documents)
    merged["info"] = {
        "title": settings.app_name,
        "version": "0.2.0",
        "description": (
            "Unified API documentation for the Multimodal RAG microservices. "
            "All /api/v1/* requests are served through this gateway on port 8000."
        ),
    }
    merged["servers"] = [{"url": "/", "description": "API Gateway"}]
    return merged, all_services_loaded


@asynccontextmanager
async def prewarm_aggregated_openapi(app: FastAPI, *, attempts: int = 5, delay_seconds: float = 2.0):
    getter = getattr(app, "openapi", None)
    if getter is not None:
        for attempt in range(1, attempts + 1):
            schema = getter()
            path_count = len(schema.get("paths", {}))
            if getattr(app.state, "openapi_cache_complete", False):
                logger.info("aggregated_openapi_prewarmed", attempt=attempt, path_count=path_count)
                break
            logger.warning("aggregated_openapi_prewarm_retry", attempt=attempt, path_count=path_count)
            app.openapi_schema = None
            app.state.openapi_cache_complete = False
            await asyncio.sleep(delay_seconds)
        else:
            logger.warning(
                "aggregated_openapi_prewarm_incomplete",
                path_count=len(getter().get("paths", {})),
            )
    yield


def attach_aggregated_openapi(app: FastAPI, *, builder: Callable[[], tuple[dict[str, Any], bool]] | None = None) -> None:
    app.state.openapi_cache_complete = False

    def aggregated_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None and app.state.openapi_cache_complete:
            return app.openapi_schema

        schema, complete = (builder or (lambda: build_aggregated_openapi(app)))()
        app.openapi_schema = schema
        app.state.openapi_cache_complete = complete
        logger.info(
            "aggregated_openapi_built",
            path_count=len(schema.get("paths", {})),
            tag_count=len(schema.get("tags", [])),
            complete=complete,
        )
        return schema

    app.openapi = aggregated_openapi  # type: ignore[method-assign]
