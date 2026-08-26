from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rag.chunk import chunk_parents
from rag.enrich import enrich_pictures
from rag.index import index_chunks
from rag.ingest import ingest_pdf
from rag.io_utils import read_jsonl
from rag.normalize import normalize_document

from app.config import Settings
from app.models.enums import DocumentStatus, IngestionJobStatus
from app.services.rag_runtime import normalize_qdrant_url

LOGGER = logging.getLogger(__name__)

ProgressCallback = Callable[[IngestionJobStatus, int, str], None]


def workspace_root(upload_dir: str) -> Path:
    return Path(upload_dir) / "workspaces"


def document_rag_dir(upload_dir: str, document_id: str) -> Path:
    return workspace_root(upload_dir) / document_id / "rag"


def prepare_document_pdf(document_id: str, storage_path: str, upload_dir: str) -> tuple[Path, Path]:
    root = workspace_root(upload_dir)
    doc_dir = root / document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = doc_dir / f"{document_id}.pdf"
    shutil.copy2(storage_path, pdf_path)
    return root, pdf_path


def _ensure_rag_env(app_settings: Settings) -> None:
    """Keep rag/* Settings.from_env() aligned with FastAPI config."""
    env_map = {
        "GROQ_API_KEY": app_settings.groq_api_key,
        "GROQ_BASE_URL": app_settings.groq_base_url,
        "GROQ_VISION_MODEL": app_settings.groq_vision_model,
        "EURI_API_KEY": app_settings.euri_api_key,
        "EURI_BASE_URL": app_settings.euri_base_url,
        "EURI_EMBEDDING_MODEL": app_settings.euri_embedding_model,
        "EURI_EMBEDDING_DIMENSIONS": str(app_settings.euri_embedding_dimensions),
        "QDRANT_URL": normalize_qdrant_url(app_settings.qdrant_url),
        "QDRANT_API_KEY": app_settings.qdrant_api_key,
        "QDRANT_COLLECTION": app_settings.qdrant_collection,
    }
    for key, value in env_map.items():
        if value:
            os.environ[key] = value


def run_ingestion_sync(
    *,
    document_id: str,
    storage_path: str,
    app_settings: Settings,
    on_progress: ProgressCallback | None = None,
    skip_enrich: bool = False,
) -> dict[str, Any]:
    _ensure_rag_env(app_settings)

    def progress(status: IngestionJobStatus, pct: int, step: str) -> None:
        if on_progress:
            on_progress(status, pct, step)

    progress(IngestionJobStatus.EXTRACTING, 5, "Preparing document workspace")
    root, pdf_path = prepare_document_pdf(document_id, storage_path, app_settings.upload_dir)

    progress(IngestionJobStatus.EXTRACTING, 15, "Extracting PDF with Docling")
    ingest_result = ingest_pdf(pdf_path, root)
    document_json = Path(ingest_result["document_json"])
    rag_path = document_json.parent / "rag"

    progress(IngestionJobStatus.CHUNKING, 35, "Normalizing extracted structure")
    normalize_document(document_json)

    if not skip_enrich:
        progress(IngestionJobStatus.EXTRACTING, 50, "Enriching figures with Groq vision")
        enrich_pictures(rag_path)

    progress(IngestionJobStatus.CHUNKING, 65, "Building parent-child chunks")
    chunk_parents(rag_path)

    progress(IngestionJobStatus.EMBEDDING, 80, "Generating embeddings")
    progress(IngestionJobStatus.INDEXING, 90, "Indexing vectors in Qdrant")
    index_manifest = index_chunks(rag_path)

    parents = read_jsonl(rag_path / "parents.jsonl")
    children = read_jsonl(rag_path / "children.jsonl")
    progress(IngestionJobStatus.COMPLETED, 100, "Ingestion complete")

    return {
        "rag_path": str(rag_path),
        "parents": parents,
        "children": children,
        "indexed_count": index_manifest.get("indexed_count", len(children)),
    }


def map_job_status_to_document_status(status: IngestionJobStatus) -> DocumentStatus:
    mapping = {
        IngestionJobStatus.QUEUED: DocumentStatus.QUEUED,
        IngestionJobStatus.EXTRACTING: DocumentStatus.EXTRACTING,
        IngestionJobStatus.CHUNKING: DocumentStatus.CHUNKING,
        IngestionJobStatus.EMBEDDING: DocumentStatus.EMBEDDING,
        IngestionJobStatus.INDEXING: DocumentStatus.INDEXING,
        IngestionJobStatus.COMPLETED: DocumentStatus.READY,
        IngestionJobStatus.FAILED: DocumentStatus.FAILED_INDEXING,
    }
    return mapping.get(status, DocumentStatus.QUEUED)


def delete_document_index(document_id: str, app_settings: Settings) -> None:
    _ensure_rag_env(app_settings)
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    from rag.config import Settings as RagSettings
    from rag.index import qdrant_client

    rag_settings = RagSettings.from_env(require_qdrant=True)
    client = qdrant_client(rag_settings)
    if not client.collection_exists(rag_settings.qdrant_collection):
        return
    client.delete(
        collection_name=rag_settings.qdrant_collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        ),
        wait=True,
    )

    doc_dir = workspace_root(app_settings.upload_dir) / document_id
    if doc_dir.exists():
        shutil.rmtree(doc_dir)
