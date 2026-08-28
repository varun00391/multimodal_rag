from pathlib import Path

from app.config import Settings


def test_empty_docling_artifacts_path_is_none(monkeypatch) -> None:
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", "")
    settings = Settings(
        extraction_output_dir="output",
        extraction_database_path="data/jobs.db",
    )
    assert settings.docling_artifacts_path is None


def test_groq_visual_extraction_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_VISUAL_EXTRACTION_ENABLED", raising=False)
    monkeypatch.delenv("GROQ_VISUAL_MODEL", raising=False)
    settings = Settings(
        _env_file=None,
        extraction_output_dir="output",
        extraction_database_path="data/jobs.db",
    )
    assert settings.groq_visual_extraction_enabled is False
    assert settings.groq_visual_model == "meta-llama/llama-4-scout-17b-16e-instruct"
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", "")
    settings = Settings(
        extraction_output_dir="output",
        extraction_database_path="data/jobs.db",
    )
    assert settings.docling_artifacts_path is None


def test_docling_artifacts_path_is_kept_when_set(monkeypatch, tmp_path: Path) -> None:
    artifacts = tmp_path / "docling-models"
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", str(artifacts))
    settings = Settings(
        extraction_output_dir="output",
        extraction_database_path="data/jobs.db",
    )
    assert settings.docling_artifacts_path == artifacts
