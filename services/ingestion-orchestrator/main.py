from __future__ import annotations

from fastapi import APIRouter, Depends

from rag_shared.app_factory import create_service_app, verify_internal_token
from rag_shared.routers import ingestion as ingestion_router
from rag_shared.schemas.internal import IngestionStartRequest, IngestionStartResponse
from rag_shared.services.ingestion_orchestrator import schedule_ingestion_job

internal = APIRouter(tags=["internal"], dependencies=[Depends(verify_internal_token)])


@internal.post("/ingestion/run", response_model=IngestionStartResponse)
async def run_ingestion(payload: IngestionStartRequest) -> IngestionStartResponse:
    accepted = await schedule_ingestion_job(payload)
    return IngestionStartResponse(job_id=payload.job_id, status="accepted" if accepted else "already_running")


app = create_service_app(
    service_name="ingestion-orchestrator",
    routers=[ingestion_router.router],
    internal_routers=[internal],
    enable_session=True,
)
