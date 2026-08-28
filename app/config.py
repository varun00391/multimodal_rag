from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8010, alias="APP_PORT")
    cors_origins: str = Field(
        default=(
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:8080,http://127.0.0.1:8080"
        ),
        alias="CORS_ORIGINS",
    )

    extraction_schema_version: str = Field(default="1.0", alias="EXTRACTION_SCHEMA_VERSION")
    extraction_routing_policy_version: str = Field(
        default="1", alias="EXTRACTION_ROUTING_POLICY_VERSION"
    )
    extraction_output_dir: Path = Field(default=Path("./output"), alias="EXTRACTION_OUTPUT_DIR")
    extraction_database_path: Path = Field(
        default=Path("./data/extraction_jobs.db"), alias="EXTRACTION_DATABASE_PATH"
    )
    extraction_allow_managed_apis: bool = Field(
        default=True, alias="EXTRACTION_ALLOW_MANAGED_APIS"
    )
    extraction_max_file_bytes: int = Field(default=104_857_600, alias="EXTRACTION_MAX_FILE_BYTES")
    extraction_max_pages: int = Field(default=500, alias="EXTRACTION_MAX_PAGES")
    extraction_max_page_points: float = Field(
        default=10_000.0, alias="EXTRACTION_MAX_PAGE_POINTS"
    )
    extraction_max_rendered_pixels: int = Field(
        default=100_000_000, alias="EXTRACTION_MAX_RENDERED_PIXELS"
    )
    extraction_max_attempts_per_page: int = Field(
        default=3, alias="EXTRACTION_MAX_ATTEMPTS_PER_PAGE"
    )
    extraction_min_validation_confidence: float = Field(
        default=0.85, alias="EXTRACTION_MIN_VALIDATION_CONFIDENCE"
    )
    extraction_cache_enabled: bool = Field(default=True, alias="EXTRACTION_CACHE_ENABLED")
    extraction_cache_dir: Path | None = Field(default=None, alias="EXTRACTION_CACHE_DIR")
    extraction_benchmark_enabled: bool = Field(
        default=False, alias="EXTRACTION_BENCHMARK_ENABLED"
    )
    extraction_max_concurrent_jobs: int = Field(
        default=8, alias="EXTRACTION_MAX_CONCURRENT_JOBS"
    )
    extraction_max_inflight_jobs: int = Field(
        default=64, alias="EXTRACTION_MAX_INFLIGHT_JOBS"
    )
    extraction_circuit_failure_threshold: int = Field(
        default=3, alias="EXTRACTION_CIRCUIT_FAILURE_THRESHOLD"
    )
    extraction_circuit_recovery_seconds: float = Field(
        default=30.0, alias="EXTRACTION_CIRCUIT_RECOVERY_SECONDS"
    )
    extraction_log_json: bool = Field(default=True, alias="EXTRACTION_LOG_JSON")

    pymupdf_min_characters: int = Field(default=500, alias="PYMUPDF_MIN_CHARACTERS")
    pymupdf_min_printable_ratio: float = Field(default=0.95, alias="PYMUPDF_MIN_PRINTABLE_RATIO")
    pymupdf_max_replacement_ratio: float = Field(
        default=0.01, alias="PYMUPDF_MAX_REPLACEMENT_RATIO"
    )
    pymupdf_max_image_coverage: float = Field(default=0.35, alias="PYMUPDF_MAX_IMAGE_COVERAGE")
    pymupdf_max_layout_complexity: float = Field(
        default=0.45, alias="PYMUPDF_MAX_LAYOUT_COMPLEXITY"
    )
    pymupdf_max_concurrency: int = Field(default=4, alias="PYMUPDF_MAX_CONCURRENCY")
    docling_max_concurrency: int = Field(default=1, alias="DOCLING_MAX_CONCURRENCY")
    extraction_group_timeout_seconds: int = Field(
        default=300, alias="EXTRACTION_GROUP_TIMEOUT_SECONDS"
    )

    docling_max_pages_per_group: int = Field(default=30, alias="DOCLING_MAX_PAGES_PER_GROUP")
    docling_image_scale: float = Field(default=1.25, alias="DOCLING_IMAGE_SCALE")
    docling_generate_page_images: bool = Field(
        default=False, alias="DOCLING_GENERATE_PAGE_IMAGES"
    )
    docling_generate_picture_images: bool = Field(
        default=True, alias="DOCLING_GENERATE_PICTURE_IMAGES"
    )
    docling_table_structure: bool = Field(default=True, alias="DOCLING_TABLE_STRUCTURE")
    docling_warm_on_startup: bool = Field(default=False, alias="DOCLING_WARM_ON_STARTUP")
    docling_artifacts_path: Path | None = Field(default=None, alias="DOCLING_ARTIFACTS_PATH")

    euri_api_key: str | None = Field(default=None, alias="EURI_API_KEY")
    euri_base_url: str = Field(
        default="https://api.euron.one/api/v1/euri", alias="EURI_BASE_URL"
    )
    gemini_model_id: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL_ID")
    gemini_target_pages_per_group: int = Field(default=5, alias="GEMINI_TARGET_PAGES_PER_GROUP")
    gemini_max_pages_per_group: int = Field(default=10, alias="GEMINI_MAX_PAGES_PER_GROUP")
    gemini_max_concurrency: int = Field(default=4, alias="GEMINI_MAX_CONCURRENCY")
    gemini_request_timeout_seconds: int = Field(
        default=180, alias="GEMINI_REQUEST_TIMEOUT_SECONDS"
    )
    gemini_extraction_prompt_version: int = Field(
        default=1, alias="GEMINI_EXTRACTION_PROMPT_VERSION"
    )
    gemini_budget_guard_enabled: bool = Field(default=True, alias="GEMINI_BUDGET_GUARD_ENABLED")
    gemini_retry_backoff_seconds: float = Field(
        default=1.0, alias="GEMINI_RETRY_BACKOFF_SECONDS"
    )
    gemini_input_usd_per_million: float = Field(
        default=0.15, alias="GEMINI_INPUT_USD_PER_MILLION"
    )
    gemini_output_usd_per_million: float = Field(
        default=0.60, alias="GEMINI_OUTPUT_USD_PER_MILLION"
    )

    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL"
    )
    groq_visual_model: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct", alias="GROQ_VISUAL_MODEL"
    )
    groq_visual_extraction_enabled: bool = Field(
        default=False, alias="GROQ_VISUAL_EXTRACTION_ENABLED"
    )
    groq_visual_prompt_version: int = Field(default=1, alias="GROQ_VISUAL_PROMPT_VERSION")
    groq_max_concurrency: int = Field(default=4, alias="GROQ_MAX_CONCURRENCY")
    groq_request_timeout_seconds: int = Field(
        default=60, alias="GROQ_REQUEST_TIMEOUT_SECONDS"
    )
    groq_min_figure_coverage: float = Field(default=0.08, alias="GROQ_MIN_FIGURE_COVERAGE")
    groq_max_figure_coverage: float = Field(default=0.75, alias="GROQ_MAX_FIGURE_COVERAGE")

    @field_validator(
        "euri_api_key",
        "groq_api_key",
        "docling_artifacts_path",
        "extraction_cache_dir",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def resolved_cache_dir(self) -> Path:
        return self.extraction_cache_dir or (self.extraction_output_dir / ".cache")

    def ensure_directories(self) -> None:
        self.extraction_output_dir.mkdir(parents=True, exist_ok=True)
        self.extraction_database_path.parent.mkdir(parents=True, exist_ok=True)
        if self.extraction_cache_enabled:
            self.resolved_cache_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
