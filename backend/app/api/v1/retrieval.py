from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.api import RetrievalSearchRequest, RetrievalSearchResponse
from app.services.rag import run_retrieval_search

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalSearchResponse)
async def retrieval_search(
    payload: RetrievalSearchRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> RetrievalSearchResponse:
    return await run_retrieval_search(
        db,
        current,
        query=payload.query,
        top_k_dense=payload.top_k_dense,
        top_k_sparse=payload.top_k_sparse,
        final_top_k=payload.final_top_k,
        document_ids=payload.document_ids,
    )
