from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    workspace: Path = Field(default=Path("output"), alias="EXTRACTION_WORKSPACE")
    model_cache: Path = Field(default=Path("models"), alias="EXTRACTION_MODEL_CACHE")
    max_upload_bytes: int = Field(default=100 * 1024 * 1024, alias="EXTRACTION_MAX_UPLOAD_BYTES")
    sparse_pdf_char_threshold: int = Field(default=40, alias="EXTRACTION_SPARSE_PDF_CHARS")
    image_ocr_char_threshold: int = Field(default=40, alias="EXTRACTION_IMAGE_OCR_CHARS")
    max_table_rows: int = Field(default=5000, alias="EXTRACTION_MAX_TABLE_ROWS")
    zip_max_files: int = Field(default=100, alias="EXTRACTION_ZIP_MAX_FILES")
    zip_max_bytes: int = Field(default=200 * 1024 * 1024, alias="EXTRACTION_ZIP_MAX_BYTES")
    zip_max_depth: int = Field(default=2, alias="EXTRACTION_ZIP_MAX_DEPTH")
    video_frame_interval_seconds: float = Field(default=10.0, alias="EXTRACTION_VIDEO_FRAME_INTERVAL")
    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")

    euri_api_key: str = Field(default="", alias="EURI_API_KEY")
    euri_base_url: str = Field(
        default="https://api.euron.one/api/v1/euri",
        alias="EURI_BASE_URL",
    )
    euri_vlm_model: str = Field(default="gpt-4o-mini", alias="EURI_VLM_MODEL")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        alias="GROQ_BASE_URL",
    )
    groq_llm_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_LLM_MODEL")

    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="extraction_chunks", alias="QDRANT_COLLECTION")
    euri_embedding_model: str = Field(
        default="gemini-embedding-2-preview",
        alias="EURI_EMBEDDING_MODEL",
    )
    euri_embedding_dims: int = Field(default=768, alias="EURI_EMBEDDING_DIMS")
    rag_chunk_chars: int = Field(default=800, alias="RAG_CHUNK_CHARS")
    rag_chunk_overlap: int = Field(default=120, alias="RAG_CHUNK_OVERLAP")
    rag_child_top_k: int = Field(default=8, alias="RAG_CHILD_TOP_K")
    rag_parent_limit: int = Field(default=3, alias="RAG_PARENT_LIMIT")
    rag_score_cutoff: float = Field(default=0.40, alias="RAG_SCORE_CUTOFF")
    rag_hybrid_prefetch: int = Field(default=20, alias="RAG_HYBRID_PREFETCH")
    rag_rrf_k: int = Field(default=60, alias="RAG_RRF_K")

    @field_validator(
        "euri_api_key",
        "groq_api_key",
        "qdrant_api_key",
        "qdrant_url",
        "euri_base_url",
        mode="before",
    )
    @classmethod
    def _strip_secrets(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @property
    def jobs_db_path(self) -> Path:
        return self.workspace / "jobs.sqlite"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.workspace.mkdir(parents=True, exist_ok=True)
    settings.model_cache.mkdir(parents=True, exist_ok=True)
    return settings
