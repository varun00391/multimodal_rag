from __future__ import annotations

from fastapi import APIRouter, Depends

from rag_shared.app_factory import create_service_app, verify_internal_token
from rag_shared.schemas.internal import SparseSearchRequest, SparseSearchResponse

from rag.retrieve import bm25_tokens
from rank_bm25 import BM25Okapi

internal = APIRouter(tags=["internal"], dependencies=[Depends(verify_internal_token)])


@internal.post("/retrieval/sparse", response_model=SparseSearchResponse)
def sparse_search(payload: SparseSearchRequest) -> SparseSearchResponse:
    if not payload.children:
        return SparseSearchResponse(results=[])

    corpus = [bm25_tokens(str(child.get("content") or "")) for child in payload.children]
    bm25 = BM25Okapi(corpus)
    query_tokens = bm25_tokens(payload.query)
    scores = bm25.get_scores(query_tokens)
    ranked = sorted(
        enumerate(scores),
        key=lambda item: item[1],
        reverse=True,
    )[: payload.top_k]

    results = []
    for rank, (index, score) in enumerate(ranked, start=1):
        child = payload.children[index]
        results.append(
            {
                "child_id": child.get("id"),
                "child": child,
                "score": float(score),
                "lexical_rank": rank,
            }
        )
    return SparseSearchResponse(results=results)


app = create_service_app(service_name="sparse-retrieval", internal_routers=[internal])
