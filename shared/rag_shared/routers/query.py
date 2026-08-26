import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_shared.core.deps import CurrentUser, get_current_user
from rag_shared.core.errors import AppError
from rag_shared.db.session import get_db
from rag_shared.models.entities import QueryRecord
from rag_shared.schemas.api import QueryRequest, QueryResponse, QuerySource, QueryUsage
from rag_shared.services.rag import run_rag_query

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query_rag(
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> QueryResponse:
    response = await run_rag_query(
        db,
        current,
        query=payload.query,
        document_ids=payload.document_ids,
        conversation_id=payload.conversation_id,
    )
    await db.commit()
    return response


@router.post("/stream")
async def query_rag_stream(
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    response = await run_rag_query(
        db,
        current,
        query=payload.query,
        document_ids=payload.document_ids,
        conversation_id=payload.conversation_id,
    )
    await db.commit()

    async def event_generator():
        yield f"data: {json.dumps({'query_id': response.query_id, 'chunk': response.answer})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> QueryResponse:
    result = await db.execute(select(QueryRecord).where(QueryRecord.id == query_id))
    record = result.scalar_one_or_none()
    if not record:
        raise AppError("DOCUMENT_NOT_FOUND", "Query not found.", status_code=404)
    if record.user_id != current.user_id and not (current.is_super_admin or current.is_admin):
        raise AppError("NOT_AUTHORIZED", "You cannot access this query.", status_code=403)

    sources = [QuerySource(**s) for s in json.loads(record.sources_json or "[]")]
    return QueryResponse(
        query_id=record.id,
        answer=record.answer or "",
        sources=sources,
        usage=QueryUsage(retrieved_chunks=len(sources)),
    )
