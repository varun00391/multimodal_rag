from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "pdf-extractor"
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "*"

    storage_backend: str = "local"
    storage_root: str = "./data"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_prefix: str = "extraction"

    database_url: str = "sqlite:///./data/extractor.db"

    worker_mode: str = "external"
    worker_poll_seconds: float = 2.0
    worker_claim_batch: int = 1

    max_pdf_size_mb: int = 50
    max_pages: int = 200

    render_dpi: int = 200
    render_image_format: str = "png"

    ocr_enabled: bool = True
    ocr_engine: str = "tesseract"
    ocr_languages: str = "eng"
    tesseract_cmd: str = "tesseract"
    paddle_ocr_use_gpu: bool = False
    paddle_ocr_lang: str = "en"

    table_engine: str = "pymupdf"
    docling_enabled: bool = False

    layout_engine: str = "pymupdf"

    vlm_enabled: bool = False
    vlm_provider: str = "openai"
    vlm_api_key: str = ""
    vlm_base_url: str = "https://api.openai.com/v1"
    vlm_model: str = "gpt-4o-mini"
    vlm_timeout_seconds: int = 60
    vlm_max_tokens: int = 2048
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    min_native_text_chars: int = 20
    scanned_text_density_threshold: int = 50
    native_text_garbage_ratio: float = 0.35

    confidence_high: float = 0.90
    confidence_medium: float = 0.75
    review_confidence_threshold: float = 0.75
    halt_pipeline_on_review: bool = False
    enable_arithmetic_checks: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.api_cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def storage_root_path(self) -> Path:
        path = Path(self.storage_root)
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path.resolve()

    @property
    def sqlite_path(self) -> Path:
        url = self.database_url
        if url.startswith("sqlite:////"):
            return Path(url.replace("sqlite:///", "", 1)).resolve()
        if url.startswith("sqlite:///"):
            relative = url.removeprefix("sqlite:///")
            path = Path(relative)
            if not path.is_absolute():
                path = ROOT_DIR / path
            return path.resolve()
        return self.storage_root_path / "extractor.db"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_root_path.mkdir(parents=True, exist_ok=True)
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
