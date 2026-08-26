from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends

from rag_shared.app_factory import create_service_app, verify_internal_token
from rag_shared.config import get_settings
from rag_shared.core.deps import CurrentUser, get_current_user
from rag_shared.db.session import get_db
from rag_shared.rag_env import ensure_rag_env
from rag_shared.schemas.api import RetrievalSearchRequest, RetrievalSearchResponse, RetrievalResultItem
from rag_shared.schemas.internal import HybridRetrievalRequest, HybridRetrievalResponse, RetrievalHitPayload
from rag_shared.services.rag import run_retrieval_search
from rag_shared.services.rag_settings import to_rag_settings

from rag.retrieve import RetrievalHit, retrieve_hits
from sqlalchemy.ext.asyncio import AsyncSession

public = APIRouter(prefix="/retrieval", tags=["retrieval"])
internal = APIRouter(tags=["internal"], dependencies=[Depends(verify_internal_token)])


def _hit_to_payload(hit: RetrievalHit) -> RetrievalHitPayload:
    return RetrievalHitPayload(
        child=hit.child,
        parent=hit.parent,
        fusion_score=hit.fusion_score,
        dense_rank=hit.dense_rank,
        lexical_rank=hit.lexical_rank,
    )


def _payload_to_hit(payload: RetrievalHitPayload) -> RetrievalHit:
    return RetrievalHit(
        child=payload.child,
        parent=payload.parent,
        fusion_score=payload.fusion_score,
        dense_rank=payload.dense_rank,
        lexical_rank=payload.lexical_rank,
    )


@public.post("/search", response_model=RetrievalSearchResponse)
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


@internal.post("/retrieval/hybrid", response_model=HybridRetrievalResponse)
def hybrid_retrieval(payload: HybridRetrievalRequest) -> HybridRetrievalResponse:
    settings = get_settings()
    ensure_rag_env(settings)
    rag_settings = to_rag_settings(settings)

    hits: list[RetrievalHit] = []
    for document_id in payload.document_ids:
        doc_children = [child for child in payload.children if child.get("document_id") == document_id]
        doc_parents = [parent for parent in payload.parents if parent.get("document_id") == document_id]
        if not doc_children or not doc_parents:
            continue
        doc_hits = retrieve_hits(
            payload.query,
            children=doc_children,
            parents=doc_parents,
            settings=rag_settings,
            candidate_limit=payload.candidate_limit,
            final_limit=payload.final_limit,
            document_id=document_id,
        )
        hits.extend(doc_hits)

    hits.sort(key=lambda hit: hit.fusion_score, reverse=True)
    deduped: list[RetrievalHit] = []
    seen_parents: set[str] = set()
    for hit in hits:
        parent_id = hit.child.get("parent_id")
        if not parent_id or parent_id in seen_parents:
            continue
        deduped.append(hit)
        seen_parents.add(parent_id)
        if len(deduped) >= payload.final_limit:
            break

    return HybridRetrievalResponse(hits=[_hit_to_payload(hit) for hit in deduped])


app = create_service_app(
    service_name="retrieval",
    routers=[public],
    internal_routers=[internal],
    init_db=True,
    enable_session=True,
)
