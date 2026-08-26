from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Response
from qdrant_client.models import FieldCondition, Filter, MatchValue

from rag_shared.app_factory import create_service_app, verify_internal_token
from rag_shared.config import get_settings
from rag_shared.rag_env import ensure_rag_env
from rag_shared.schemas.internal import (
    ChunkingRequest,
    ChunkingResponse,
    IndexUpsertRequest,
    IndexUpsertResponse,
)
from rag_shared.workspace import remove_document_workspace

from rag.chunk import chunk_parents
from rag.enrich import enrich_pictures
from rag.config import Settings as RagSettings
from rag.index import index_chunks, qdrant_client
from rag.io_utils import read_jsonl
from rag.normalize import normalize_document

LOGGER = logging.getLogger(__name__)
internal = APIRouter(tags=["internal"], dependencies=[Depends(verify_internal_token)])


@internal.post("/indexing/chunk", response_model=ChunkingResponse)
def chunk_document(payload: ChunkingRequest) -> ChunkingResponse:
    settings = get_settings()
    ensure_rag_env(settings)
    document_json = Path(payload.document_json)
    rag_path = Path(payload.rag_path)
    rag_path.mkdir(parents=True, exist_ok=True)

    normalize_document(document_json)
    if not payload.skip_enrich:
        enrich_pictures(rag_path)
    chunk_parents(rag_path)

    parents = read_jsonl(rag_path / "parents.jsonl")
    children = read_jsonl(rag_path / "children.jsonl")
    return ChunkingResponse(
        document_id=payload.document_id,
        rag_path=str(rag_path),
        parent_count=len(parents),
        child_count=len(children),
    )


@internal.post("/indexing/upsert", response_model=IndexUpsertResponse)
def upsert_index(payload: IndexUpsertRequest) -> IndexUpsertResponse:
    settings = get_settings()
    ensure_rag_env(settings)
    rag_path = Path(payload.rag_path)
    manifest = index_chunks(rag_path)
    children = read_jsonl(rag_path / "children.jsonl")
    return IndexUpsertResponse(
        document_id=payload.document_id,
        indexed_count=manifest.get("indexed_count", len(children)),
    )


@internal.delete("/indexing/documents/{document_id}", status_code=204, response_class=Response)
def delete_index_artifacts(document_id: str) -> Response:
    settings = get_settings()
    ensure_rag_env(settings)
    rag_settings = RagSettings.from_env(require_qdrant=True)
    client = qdrant_client(rag_settings)
    if client.collection_exists(rag_settings.qdrant_collection):
        client.delete(
            collection_name=rag_settings.qdrant_collection,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
            wait=True,
        )
    remove_document_workspace(document_id, settings.upload_dir)
    return Response(status_code=204)


app = create_service_app(service_name="chunking-indexing", internal_routers=[internal])
