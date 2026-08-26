import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.models.entities import QueryRecord
from app.schemas.api import QueryResponse, QuerySource, QueryUsage

router = APIRouter(tags=["users"])


@router.get("/users/me/queries", response_model=list[QueryResponse])
async def list_my_queries(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[QueryResponse]:
    result = await db.execute(
        select(QueryRecord)
        .where(QueryRecord.user_id == current.user_id)
        .order_by(QueryRecord.created_at.desc())
        .limit(50)
    )
    records = result.scalars().all()
    responses: list[QueryResponse] = []
    for record in records:
        sources = [QuerySource(**s) for s in json.loads(record.sources_json or "[]")]
        responses.append(
            QueryResponse(
                query_id=record.id,
                answer=record.answer or "",
                sources=sources,
                usage=QueryUsage(retrieved_chunks=len(sources)),
            )
        )
    return responses
