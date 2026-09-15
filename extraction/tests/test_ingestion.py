from app.ingestion.hashing import sha256_bytes
from app.ingestion.upload import validate_pdf_upload
from app.core.exceptions import InvalidUploadError


def test_sha256_bytes_is_stable():
    assert sha256_bytes(b"abc") == sha256_bytes(b"abc")
    assert sha256_bytes(b"abc") != sha256_bytes(b"abd")


def test_validate_pdf_rejects_non_pdf():
    try:
        validate_pdf_upload("note.txt", b"hello")
        assert False, "expected InvalidUploadError"
    except InvalidUploadError:
        pass


def test_validate_pdf_rejects_bad_magic():
    try:
        validate_pdf_upload("file.pdf", b"XXXX")
        assert False, "expected InvalidUploadError"
    except InvalidUploadError:
        pass
