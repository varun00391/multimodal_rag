import pytest

from app.core.config import get_settings
from app.db import repository as repository_mod


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    db_path = tmp_path / "extractor.db"
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("WORKER_MODE", "external")
    monkeypatch.setenv("OCR_ENABLED", "false")
    monkeypatch.setenv("VLM_ENABLED", "false")
    monkeypatch.setenv("DOCLING_ENABLED", "false")
    get_settings.cache_clear()
    repository_mod._REPO = None
    yield tmp_path
    get_settings.cache_clear()
    repository_mod._REPO = None
