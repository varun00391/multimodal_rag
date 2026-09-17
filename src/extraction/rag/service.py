from __future__ import annotations

from extraction.errors import ExtractionError
from extraction.intake import document_dir
from extraction.jobs.store import JobStore
from extraction.rag.answer import CANNOT_ANSWER, answer_question
from extraction.rag.chunker import chunk_document
from extraction.rag.embeddings import embed_children, embed_texts
from extraction.rag.retrieve import apply_dense_cutoff, expand_parents
from extraction.rag.store import get_chunk_store
from extraction.settings import Settings
from extraction.store import load_document


def _ready_record(jobs: JobStore, job_id: str):
    record = jobs.get(job_id)
    if record is None:
        raise ExtractionError("JOB_NOT_FOUND", "Job was not found.")
    if record.status in {"queued", "running"}:
        raise ExtractionError("JOB_NOT_READY", "Extraction job is still running.")
    return record


def index_document(settings: Settings, jobs: JobStore, job_id: str) -> dict:
    record = _ready_record(jobs, job_id)
    workspace = document_dir(settings, record.document_id)
    document = load_document(workspace)
    if document is None:
        raise ExtractionError("DOCUMENT_NOT_FOUND", "document.json is missing for this job.")
    if document.status == "failed":
        raise ExtractionError("DOCUMENT_FAILED", "Cannot index a failed extraction.")
    children = chunk_document(document, settings)
    if not children:
        raise ExtractionError("NO_CHUNKS", "The document produced no indexable chunks.")
    vectors = embed_children(settings, children, workspace / "assets")
    store = get_chunk_store(settings)
    stored = store.replace_document(document.document_id, record.job_id, children, vectors)
    parent_ids = {child.parent_id for child in children}
    return {
        "job_id": record.job_id,
        "document_id": document.document_id,
        "parent_count": len(parent_ids),
        "child_count": stored,
        "status": "indexed",
    }


def ask_question(settings: Settings, jobs: JobStore, question: str, job_id: str | None = None) -> dict:
    question = question.strip()
    if not question:
        raise ExtractionError("EMPTY_QUESTION", "Question is empty.")
    document_id = None
    if job_id:
        record = _ready_record(jobs, job_id)
        document_id = record.document_id
    query_vector = embed_texts(settings, [question])[0]
    store = get_chunk_store(settings)
    hits = store.query(
        query_vector,
        question,
        limit=settings.rag_child_top_k,
        prefetch=settings.rag_hybrid_prefetch,
        rrf_k=settings.rag_rrf_k,
        document_id=document_id,
    )
    hits = apply_dense_cutoff(hits, settings.rag_score_cutoff)
    parents = expand_parents(hits, settings.rag_parent_limit)
    if not parents:
        return {"answer": CANNOT_ANSWER, "sources": []}
    answer = answer_question(settings, question, parents)
    sources = []
    for parent in parents:
        child = parent.children[0]
        sources.append(
            {
                "filename": parent.filename,
                "parent_id": parent.parent_id,
                "parent_type": parent.parent_type,
                "unit_type": parent.unit_type,
                "unit_index": parent.unit_index,
                "score": round(parent.score, 4),
                "excerpt": child.child_text[:500],
                "asset_path": child.asset_path,
            }
        )
    return {"answer": answer, "sources": sources}
