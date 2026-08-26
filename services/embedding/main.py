from __future__ import annotations

from fastapi import APIRouter, Depends

from rag_shared.app_factory import create_service_app, verify_internal_token
from rag_shared.config import get_settings
from rag_shared.rag_env import ensure_rag_env
from rag_shared.schemas.internal import EmbeddingRequest, EmbeddingResponse

from rag.clients import euri_client
from rag.config import Settings as RagSettings
from rag.embeddings import embed_texts

internal = APIRouter(tags=["internal"], dependencies=[Depends(verify_internal_token)])


@internal.post("/indexing/embed", response_model=EmbeddingResponse)
def embed_chunks(payload: EmbeddingRequest) -> EmbeddingResponse:
    settings = get_settings()
    ensure_rag_env(settings)
    rag_settings = RagSettings.from_env()
    client = euri_client(rag_settings)
    vectors = embed_texts(client, rag_settings, payload.texts, batch_size=payload.batch_size)
    return EmbeddingResponse(
        embeddings=vectors,
        model=rag_settings.embedding_model,
        dimensions=rag_settings.embedding_dimensions,
    )


app = create_service_app(service_name="embedding", internal_routers=[internal])
