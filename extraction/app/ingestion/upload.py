from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, InvalidUploadError
from app.core.ids import document_id, job_id
from app.db.repository import Repository
from app.ingestion.hashing import sha256_bytes
from app.ingestion.storage import get_storage
from app.models.common import JobStatus
from app.models.document import DocumentRecord, JobRecord

PDF_MAGIC = b"%PDF"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_pdf_upload(filename: str, data: bytes) -> None:
    settings = get_settings()
    if not filename.lower().endswith(".pdf"):
        raise InvalidUploadError("Only PDF files are accepted.")
    if not data.startswith(PDF_MAGIC):
        raise InvalidUploadError("File is not a valid PDF.")
    max_bytes = settings.max_pdf_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise FileTooLargeError(
            f"PDF exceeds the {settings.max_pdf_size_mb} MB size limit."
        )


def ingest_pdf(filename: str, data: bytes, repo: Repository) -> tuple[DocumentRecord, JobRecord]:
    validate_pdf_upload(filename, data)
    now = utcnow()
    doc_id = document_id()
    jb_id = job_id()
    digest = sha256_bytes(data)
    storage = get_storage()
    storage.save_original(doc_id, data)

    document = DocumentRecord(
        id=doc_id,
        filename=Path(filename).name,
        sha256=digest,
        size_bytes=len(data),
        status=JobStatus.QUEUED,
        job_id=jb_id,
        created_at=now,
        updated_at=now,
    )
    job = JobRecord(
        id=jb_id,
        document_id=doc_id,
        status=JobStatus.QUEUED,
        current_step="queued",
        created_at=now,
        updated_at=now,
    )
    repo.create_document(document)
    repo.create_job(job)
    return document, job
