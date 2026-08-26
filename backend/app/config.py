from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Multimodal RAG API"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    internal_prefix: str = "/internal/v1"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://rag:rag@postgres:5432/multimodal_rag",
        alias="DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    # Auth
    super_admin_email: str = Field(..., alias="SUPER_ADMIN_EMAIL")
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    session_secret_key: str = Field(..., alias="SESSION_SECRET_KEY")
    oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/google/callback",
        alias="OAUTH_REDIRECT_URI",
    )
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")

    # Storage
    upload_dir: str = Field(default="/data/uploads", alias="UPLOAD_DIR")
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")

    # External providers (optional at startup; required for full RAG pipeline)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        alias="GROQ_BASE_URL",
    )
    groq_vision_model: str = Field(default="qwen/qwen3.6-27b", alias="GROQ_VISION_MODEL")
    euri_api_key: str = Field(default="", alias="EURI_API_KEY")
    euri_base_url: str = Field(
        default="https://api.euron.one/api/v1/euri",
        alias="EURI_BASE_URL",
    )
    euri_embedding_model: str = Field(
        default="gemini-embedding-001",
        alias="EURI_EMBEDDING_MODEL",
    )
    euri_embedding_dimensions: int = Field(default=768, alias="EURI_EMBEDDING_DIMENSIONS")
    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(
        default="docling_multimodal_rag",
        alias="QDRANT_COLLECTION",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
