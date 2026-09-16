from __future__ import annotations

from pathlib import Path

import pytest

from extraction.settings import get_settings


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EXTRACTION_WORKSPACE", str(tmp_path / "output"))
    monkeypatch.setenv("EXTRACTION_MODEL_CACHE", str(tmp_path / "models"))
    monkeypatch.setenv("EURI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()
