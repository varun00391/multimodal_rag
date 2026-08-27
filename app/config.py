from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    extraction_benchmark_enabled: bool = Field(
        default=False, alias="EXTRACTION_BENCHMARK_ENABLED"
    )

    pymupdf_min_characters: int = Field(default=500, alias="PYMUPDF_MIN_CHARACTERS")
    pymupdf_min_printable_ratio: float = Field(default=0.95, alias="PYMUPDF_MIN_PRINTABLE_RATIO")
    pymupdf_max_replacement_ratio: float = Field(
        default=0.01, alias="PYMUPDF_MAX_REPLACEMENT_RATIO"
    )
    pymupdf_max_image_coverage: float = Field(default=0.35, alias="PYMUPDF_MAX_IMAGE_COVERAGE")
    pymupdf_max_layout_complexity: float = Field(
        default=0.45, alias="PYMUPDF_MAX_LAYOUT_COMPLEXITY"
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

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
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

    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_visual_model: str | None = Field(default=None, alias="GROQ_VISUAL_MODEL")
    groq_visual_extraction_enabled: bool = Field(
        default=False, alias="GROQ_VISUAL_EXTRACTION_ENABLED"
    )
    groq_visual_prompt_version: int = Field(default=1, alias="GROQ_VISUAL_PROMPT_VERSION")

    def ensure_directories(self) -> None:
        self.extraction_output_dir.mkdir(parents=True, exist_ok=True)
        self.extraction_database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
