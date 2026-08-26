from typing import Any

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    document_id: str
    storage_path: str
    upload_dir: str


class ExtractionResponse(BaseModel):
    document_id: str
    document_json: str
    rag_path: str
    status: str = "completed"


class ChunkingRequest(BaseModel):
    document_id: str
    document_json: str
    rag_path: str
    skip_enrich: bool = False


class ChunkingResponse(BaseModel):
    document_id: str
    rag_path: str
    parent_count: int
    child_count: int
    status: str = "completed"


class EmbeddingRequest(BaseModel):
    texts: list[str]
    batch_size: int = 32


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dimensions: int


class IndexUpsertRequest(BaseModel):
    document_id: str
    rag_path: str
    department_id: str | None = None
    owner_user_id: str | None = None


class IndexUpsertResponse(BaseModel):
    document_id: str
    indexed_count: int
    status: str = "completed"


class IndexDeleteRequest(BaseModel):
    document_id: str


class SparseSearchRequest(BaseModel):
    query: str
    children: list[dict[str, Any]]
    top_k: int = 10


class SparseSearchResponse(BaseModel):
    results: list[dict[str, Any]]


class HybridRetrievalRequest(BaseModel):
    query: str
    children: list[dict[str, Any]]
    parents: list[dict[str, Any]]
    document_ids: list[str]
    candidate_limit: int = 25
    final_limit: int = 7


class RetrievalHitPayload(BaseModel):
    child: dict[str, Any]
    parent: dict[str, Any]
    fusion_score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None


class HybridRetrievalResponse(BaseModel):
    hits: list[RetrievalHitPayload]


class GenerationContextItem(BaseModel):
    type: str
    content: str | None = None
    image_ref: str | None = None
    page: int | None = None


class GenerationRequest(BaseModel):
    query: str
    hits: list[RetrievalHitPayload]
    style: str = "detailed"


class GenerationResponse(BaseModel):
    answer: str
    model: str | None = None


class IngestionStartRequest(BaseModel):
    job_id: str
    document_id: str
    storage_path: str
    department_id: str | None = None
    owner_user_id: str | None = None


class IngestionStartResponse(BaseModel):
    job_id: str
    status: str = "accepted"


class JobEventPayload(BaseModel):
    job_id: str
    document_id: str
    status: str
    progress: int
    current_step: str | None = None
    error_message: str | None = None
