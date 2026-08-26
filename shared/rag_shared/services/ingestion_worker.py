from __future__ import annotations

import httpx

from rag_shared.clients.pipeline import PipelineClient
from rag_shared.config import get_settings
from rag_shared.schemas.internal import IngestionStartRequest


async def schedule_ingestion_job(
    *,
    job_id: str,
    document_id: str,
    storage_path: str,
    department_id: str | None = None,
    owner_user_id: str | None = None,
) -> bool:
    settings = get_settings()
    request = IngestionStartRequest(
        job_id=job_id,
        document_id=document_id,
        storage_path=storage_path,
        department_id=department_id,
        owner_user_id=owner_user_id,
    )
    client = PipelineClient(settings)
    try:
        result = await client.start_ingestion(request)
        return result.status == "accepted"
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 409:
            return False
        raise
