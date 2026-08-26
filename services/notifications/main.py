from __future__ import annotations

import json
import logging
from typing import Any

import redis
from fastapi import APIRouter, Depends

from rag_shared.app_factory import create_service_app, verify_internal_token
from rag_shared.config import get_settings
from rag_shared.schemas.internal import JobEventPayload

LOGGER = logging.getLogger(__name__)
internal = APIRouter(tags=["internal"], dependencies=[Depends(verify_internal_token)])
public = APIRouter(prefix="/notifications", tags=["notifications"])

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


@internal.post("/notifications/job-event")
def publish_job_event(payload: JobEventPayload) -> dict[str, str]:
    channel = f"ingestion:{payload.job_id}"
    _get_redis().publish(channel, payload.model_dump_json())
    _get_redis().setex(f"job-status:{payload.job_id}", 86400, payload.model_dump_json())
    LOGGER.info("job_event_published", job_id=payload.job_id, status=payload.status)
    return {"status": "published"}


@public.get("/jobs/{job_id}")
def get_job_notification(job_id: str) -> dict[str, Any]:
    raw = _get_redis().get(f"job-status:{job_id}")
    if not raw:
        return {"job_id": job_id, "status": "unknown"}
    return json.loads(raw)


app = create_service_app(
    service_name="notifications",
    routers=[public],
    internal_routers=[internal],
)
