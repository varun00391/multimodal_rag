from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import CurrentUser
from app.core.errors import AppError
from app.models.entities import Document, QueryRecord
from app.schemas.api import QueryResponse, QuerySource, QueryUsage, RetrievalResultItem, RetrievalSearchResponse
from app.services.ingestion_pipeline import document_rag_dir
from app.services.rag_runtime import TRANSIENT_RETRIEVAL_ERRORS, call_with_retries
from app.services.rag_settings import to_rag_settings
from rag.generate import generate_answer
from rag.io_utils import read_jsonl
from rag.retrieve import RetrievalHit, retrieve_hits

LOGGER = logging.getLogger(__name__)


async def _get_accessible_documents(
    db: AsyncSession,
    current: CurrentUser,
    *,
    document_ids: list[str] | None,
    require_ready: bool = True,
) -> list[Document]:
    stmt = select(Document)
    if require_ready:
        from app.models.enums import DocumentStatus

        stmt = stmt.where(Document.status == DocumentStatus.READY)
    if not current.is_super_admin:
        if not current.department_ids:
            return []
        stmt = stmt.where(Document.department_id.in_(current.department_ids))
    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))
    result = await db.execute(stmt.order_by(Document.created_at.desc()))
    documents = list(result.scalars().all())
    if document_ids and len(documents) != len(set(document_ids)):
        raise AppError("DOCUMENT_ACCESS_DENIED", "One or more documents are unavailable.", status_code=403)
    return documents


def _load_corpus(upload_dir: str, documents: list[Document]) -> tuple[list[dict], list[dict]]:
    children: list[dict] = []
    parents: list[dict] = []
    for document in documents:
        rag_path = document_rag_dir(upload_dir, document.id)
        children_file = rag_path / "children.jsonl"
        parents_file = rag_path / "parents.jsonl"
        if not children_file.is_file() or not parents_file.is_file():
            LOGGER.warning("missing_rag_artifacts", document_id=document.id, rag_path=str(rag_path))
            continue
        children.extend(read_jsonl(children_file))
        parents.extend(read_jsonl(parents_file))
    return children, parents


def _retrieve_scoped_hits(
    query: str,
    *,
    children: list[dict],
    parents: list[dict],
    document_ids: list[str],
    candidate_limit: int,
    final_limit: int,
) -> list[RetrievalHit]:
    settings = to_rag_settings(get_settings())
    if not settings.groq_api_key or not settings.euri_api_key or not settings.qdrant_url:
        raise AppError(
            "INTERNAL_ERROR",
            "RAG providers are not configured. Set GROQ_API_KEY, EURI_API_KEY, and QDRANT_URL.",
            status_code=503,
        )

    hits: list[RetrievalHit] = []
    for document_id in document_ids:
        doc_children = [child for child in children if child.get("document_id") == document_id]
        doc_parents = [parent for parent in parents if parent.get("document_id") == document_id]
        if not doc_children or not doc_parents:
            continue
        try:
            doc_hits = call_with_retries(
                lambda document_id=document_id, doc_children=doc_children, doc_parents=doc_parents: retrieve_hits(
                    query,
                    children=doc_children,
                    parents=doc_parents,
                    settings=settings,
                    candidate_limit=candidate_limit,
                    final_limit=final_limit,
                    document_id=document_id,
                )
            )
        except TRANSIENT_RETRIEVAL_ERRORS as error:
            LOGGER.exception("retrieval_vector_search_failed", document_id=document_id)
            raise AppError(
                "RETRIEVAL_FAILED",
                f"Vector search failed while contacting Qdrant: {error}",
                status_code=503,
            ) from error
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
        if len(deduped) >= final_limit:
            break
    return deduped


def _hit_to_source(hit: RetrievalHit) -> QuerySource:
    parent = hit.parent
    return QuerySource(
        document_id=str(parent.get("document_id") or ""),
        page=parent.get("page_start"),
        chunk_id=str(hit.child.get("id") or ""),
        element_type=str(parent.get("modality") or "text"),
    )


def _hit_to_result(hit: RetrievalHit) -> RetrievalResultItem:
    parent = hit.parent
    sources: list[str] = []
    if hit.dense_rank is not None:
        sources.append("dense")
    if hit.lexical_rank is not None:
        sources.append("sparse")
    return RetrievalResultItem(
        chunk_id=str(hit.child.get("id") or ""),
        document_id=str(parent.get("document_id") or ""),
        page=parent.get("page_start"),
        element_type=str(parent.get("modality") or "text"),
        score=hit.fusion_score,
        retrieval_sources=sources,
    )


async def run_retrieval_search(
    db: AsyncSession,
    current: CurrentUser,
    *,
    query: str,
    top_k_dense: int,
    top_k_sparse: int,
    final_top_k: int,
    document_ids: list[str] | None,
) -> RetrievalSearchResponse:
    settings = get_settings()
    documents = await _get_accessible_documents(db, current, document_ids=document_ids)
    if not documents:
        return RetrievalSearchResponse(results=[])

    children, parents = _load_corpus(settings.upload_dir, documents)
    if not children:
        return RetrievalSearchResponse(results=[])

    candidate_limit = max(top_k_dense, top_k_sparse, final_top_k)
    hits = await asyncio.to_thread(
        _retrieve_scoped_hits,
        query,
        children=children,
        parents=parents,
        document_ids=[doc.id for doc in documents],
        candidate_limit=candidate_limit,
        final_limit=final_top_k,
    )
    return RetrievalSearchResponse(results=[_hit_to_result(hit) for hit in hits])


async def run_rag_query(
    db: AsyncSession,
    current: CurrentUser,
    *,
    query: str,
    document_ids: list[str] | None,
    conversation_id: str | None,
) -> QueryResponse:
    settings = get_settings()
    documents = await _get_accessible_documents(db, current, document_ids=document_ids)
    if not documents:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "No indexed documents are available for query. Upload a PDF and wait for ingestion to complete.",
            status_code=404,
        )

    children, parents = _load_corpus(settings.upload_dir, documents)
    if not children:
        raise AppError(
            "INGESTION_FAILED",
            "Documents exist but indexing artifacts are missing. Re-run ingestion.",
            status_code=409,
        )

    hits = await asyncio.to_thread(
        _retrieve_scoped_hits,
        query,
        children=children,
        parents=parents,
        document_ids=[doc.id for doc in documents],
        candidate_limit=25,
        final_limit=7,
    )
    rag_settings = to_rag_settings(settings)
    answer = await asyncio.to_thread(generate_answer, query, hits, rag_settings, style="detailed")
    sources = [_hit_to_source(hit) for hit in hits]

    record = QueryRecord(
        user_id=current.user_id,
        query_text=query,
        answer=answer.text,
        sources_json=json.dumps([source.model_dump() for source in sources]),
        conversation_id=conversation_id,
    )
    db.add(record)
    await db.flush()

    return QueryResponse(
        query_id=record.id,
        answer=answer.text,
        sources=sources,
        usage=QueryUsage(retrieved_chunks=len(sources)),
    )
