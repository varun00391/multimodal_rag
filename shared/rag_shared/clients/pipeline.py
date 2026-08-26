from __future__ import annotations

import httpx

from rag_shared.config import Settings, get_settings
from rag_shared.core.errors import AppError
from rag_shared.schemas.internal import (
    ChunkingRequest,
    ChunkingResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ExtractionRequest,
    ExtractionResponse,
    GenerationRequest,
    GenerationResponse,
    HybridRetrievalRequest,
    HybridRetrievalResponse,
    IndexDeleteRequest,
    IndexUpsertRequest,
    IndexUpsertResponse,
    IngestionStartRequest,
    IngestionStartResponse,
    SparseSearchRequest,
    SparseSearchResponse,
)


class PipelineClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._headers = {"X-Internal-Token": self.settings.internal_service_token}

    async def _post(self, url: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(url, json=payload, headers=self._headers)
            if response.is_error:
                raise AppError(
                    "UPSTREAM_ERROR",
                    f"Upstream request failed ({response.status_code}) at {url}: {response.text[:500]}",
                    status_code=502,
                )
            return response.json()

    async def _delete(self, url: str, payload: dict | None = None) -> None:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.request("DELETE", url, json=payload, headers=self._headers)
            response.raise_for_status()

    async def start_ingestion(self, request: IngestionStartRequest) -> IngestionStartResponse:
        data = await self._post(
            f"{self.settings.ingestion_service_url}/internal/v1/ingestion/run",
            request.model_dump(),
        )
        return IngestionStartResponse.model_validate(data)

    async def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        data = await self._post(
            f"{self.settings.extraction_service_url}/internal/v1/extraction/extract",
            request.model_dump(),
        )
        return ExtractionResponse.model_validate(data)

    async def chunk(self, request: ChunkingRequest) -> ChunkingResponse:
        data = await self._post(
            f"{self.settings.chunking_service_url}/internal/v1/indexing/chunk",
            request.model_dump(),
        )
        return ChunkingResponse.model_validate(data)

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        data = await self._post(
            f"{self.settings.embedding_service_url}/internal/v1/indexing/embed",
            request.model_dump(),
        )
        return EmbeddingResponse.model_validate(data)

    async def upsert_index(self, request: IndexUpsertRequest) -> IndexUpsertResponse:
        data = await self._post(
            f"{self.settings.chunking_service_url}/internal/v1/indexing/upsert",
            request.model_dump(),
        )
        return IndexUpsertResponse.model_validate(data)

    async def delete_index(self, request: IndexDeleteRequest) -> None:
        await self._delete(
            f"{self.settings.chunking_service_url}/internal/v1/indexing/documents/{request.document_id}",
        )

    async def sparse_search(self, request: SparseSearchRequest) -> SparseSearchResponse:
        data = await self._post(
            f"{self.settings.sparse_retrieval_service_url}/internal/v1/retrieval/sparse",
            request.model_dump(),
        )
        return SparseSearchResponse.model_validate(data)

    async def hybrid_retrieval(self, request: HybridRetrievalRequest) -> HybridRetrievalResponse:
        data = await self._post(
            f"{self.settings.retrieval_service_url}/internal/v1/retrieval/hybrid",
            request.model_dump(),
        )
        return HybridRetrievalResponse.model_validate(data)

    async def generate_answer(self, request: GenerationRequest) -> GenerationResponse:
        data = await self._post(
            f"{self.settings.generation_service_url}/internal/v1/generation/answer",
            request.model_dump(),
        )
        return GenerationResponse.model_validate(data)
