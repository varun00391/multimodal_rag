import io

import fitz
import pytest

from app.config import Settings
from app.errors import InputValidationError
from app.storage.workspace import InputValidator


def make_pdf_bytes(text: str = "Validation test") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def test_validate_upload_bytes_accepts_valid_pdf(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        extraction_output_dir=tmp_path / "output",
        extraction_database_path=tmp_path / "data" / "jobs.db",
    )
    validator = InputValidator(settings)
    result = validator.validate_upload_bytes(
        make_pdf_bytes(),
        content_type="application/pdf",
    )
    assert result.page_count == 1
    assert len(result.sha256) == 64


def test_validate_upload_bytes_rejects_bad_signature(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        extraction_output_dir=tmp_path / "output",
        extraction_database_path=tmp_path / "data" / "jobs.db",
    )
    validator = InputValidator(settings)
    with pytest.raises(InputValidationError) as exc_info:
        validator.validate_upload_bytes(b"hello", content_type="application/pdf")
    assert exc_info.value.code == "INVALID_PDF_SIGNATURE"
