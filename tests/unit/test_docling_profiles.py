import os

import pytest

from app.adapters.docling_profiles import (
    DEFAULT_PROFILE,
    PROFILE_DIGITAL_LAYOUT,
    PROFILE_DIGITAL_TABLE,
    PROFILE_FORMULA_CODE,
    PROFILE_PRIVATE_OCR,
    apply_docling_artifacts_path,
    parse_extractor_ref,
    pipeline_flags,
    resolve_docling_profile,
)
from app.config import Settings


def test_profiles_enable_only_required_capabilities() -> None:
    layout = pipeline_flags(PROFILE_DIGITAL_LAYOUT)
    table = pipeline_flags(PROFILE_DIGITAL_TABLE)
    formula = pipeline_flags(PROFILE_FORMULA_CODE)
    ocr = pipeline_flags(PROFILE_PRIVATE_OCR)

    assert layout == {
        "do_ocr": False,
        "do_table_structure": False,
        "do_code_enrichment": False,
        "do_formula_enrichment": False,
        "generate_page_images": False,
    }
    assert table["do_table_structure"] is True
    assert table["do_ocr"] is False
    assert formula["do_code_enrichment"] is True
    assert formula["do_formula_enrichment"] is True
    assert formula["do_table_structure"] is True
    assert ocr["do_ocr"] is True
    assert ocr["do_table_structure"] is True
    assert ocr["generate_page_images"] is False


def test_force_extractor_refs_resolve_to_named_profiles() -> None:
    assert parse_extractor_ref("pymupdf") == ("pymupdf", None)
    assert parse_extractor_ref("docling") == ("docling", None)
    assert parse_extractor_ref("docling:digital-table") == ("docling", "digital-table")
    assert resolve_docling_profile("docling") == DEFAULT_PROFILE
    assert resolve_docling_profile("docling:private-ocr") == PROFILE_PRIVATE_OCR
    assert resolve_docling_profile("pymupdf") is None


def test_empty_artifacts_env_does_not_pin_docling_to_cwd(monkeypatch) -> None:
    pytest.importorskip("docling")
    from docling.datamodel.settings import settings as docling_settings

    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", "")
    previous = docling_settings.artifacts_path
    try:
        settings = Settings(
            extraction_output_dir="output",
            extraction_database_path="data/jobs.db",
        )
        apply_docling_artifacts_path(settings)
        assert settings.docling_artifacts_path is None
        assert docling_settings.artifacts_path is None
        assert os.environ.get("DOCLING_ARTIFACTS_PATH") in (None, "")
        assert not os.environ.get("DOCLING_ARTIFACTS_PATH")
    finally:
        docling_settings.artifacts_path = previous
