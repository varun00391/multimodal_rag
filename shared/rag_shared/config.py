from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Multimodal RAG"
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
    super_admin_email: str = Field(default="", alias="SUPER_ADMIN_EMAIL")
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    session_secret_key: str = Field(default="change-me", alias="SESSION_SECRET_KEY")
    oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/google/callback",
        alias="OAUTH_REDIRECT_URI",
    )
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")

    # Storage
    upload_dir: str = Field(default="/data/uploads", alias="UPLOAD_DIR")
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")

    # External providers
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    groq_vision_model: str = Field(default="qwen/qwen3.6-27b", alias="GROQ_VISION_MODEL")
    euri_api_key: str = Field(default="", alias="EURI_API_KEY")
    euri_base_url: str = Field(default="https://api.euron.one/api/v1/euri", alias="EURI_BASE_URL")
    euri_embedding_model: str = Field(default="gemini-embedding-001", alias="EURI_EMBEDDING_MODEL")
    euri_embedding_dimensions: int = Field(default=768, alias="EURI_EMBEDDING_DIMENSIONS")
    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="docling_multimodal_rag", alias="QDRANT_COLLECTION")

    # Inter-service communication
    internal_service_token: str = Field(default="dev-internal-token", alias="INTERNAL_SERVICE_TOKEN")
    auth_service_url: str = Field(default="http://auth:8001", alias="AUTH_SERVICE_URL")
    user_management_service_url: str = Field(
        default="http://user-management:8002", alias="USER_MANAGEMENT_SERVICE_URL"
    )
    documents_service_url: str = Field(default="http://documents:8003", alias="DOCUMENTS_SERVICE_URL")
    ingestion_service_url: str = Field(
        default="http://ingestion-orchestrator:8004", alias="INGESTION_SERVICE_URL"
    )
    extraction_service_url: str = Field(default="http://extraction:8010", alias="EXTRACTION_SERVICE_URL")
    chunking_service_url: str = Field(default="http://chunking-indexing:8011", alias="CHUNKING_SERVICE_URL")
    embedding_service_url: str = Field(default="http://embedding:8012", alias="EMBEDDING_SERVICE_URL")
    sparse_retrieval_service_url: str = Field(
        default="http://sparse-retrieval:8013", alias="SPARSE_RETRIEVAL_SERVICE_URL"
    )
    retrieval_service_url: str = Field(default="http://retrieval:8014", alias="RETRIEVAL_SERVICE_URL")
    generation_service_url: str = Field(default="http://generation:8015", alias="GENERATION_SERVICE_URL")
    query_service_url: str = Field(default="http://query:8016", alias="QUERY_SERVICE_URL")
    dashboard_service_url: str = Field(default="http://dashboard:8017", alias="DASHBOARD_SERVICE_URL")
    notifications_service_url: str = Field(
        default="http://notifications:8018", alias="NOTIFICATIONS_SERVICE_URL"
    )

    # Feature flags
    use_microservices_pipeline: bool = Field(default=True, alias="USE_MICROSERVICES_PIPELINE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
