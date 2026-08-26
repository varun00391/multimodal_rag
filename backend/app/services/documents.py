from __future__ import annotations

import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.core.deps import CurrentUser
from app.core.errors import AppError
from app.models.entities import Department, Document, DocumentElement, IngestionJob
from app.models.enums import DocumentStatus, IngestionJobStatus
from app.schemas.api import DocumentElementResponse, DocumentResponse, IngestionJobResponse


def _document_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        document_id=doc.id,
        title=doc.title,
        filename=doc.filename,
        status=doc.status.value,
        department_id=doc.department_id,
        owner_user_id=doc.owner_user_id,
        size_bytes=doc.size_bytes,
    )


def _job_response(job: IngestionJob) -> IngestionJobResponse:
    return IngestionJobResponse(
        job_id=job.id,
        document_id=job.document_id,
        status=job.status.value,
        progress=job.progress,
        current_step=job.current_step,
    )


async def get_department(db: AsyncSession, department_id: str) -> Department:
    result = await db.execute(select(Department).where(Department.id == department_id))
    department = result.scalar_one_or_none()
    if not department:
        raise AppError(
            "DEPARTMENT_NOT_FOUND",
            "Department not found. Use the department_id UUID from GET /api/v1/departments, not the department name.",
            status_code=404,
        )
    return department


async def get_document(db: AsyncSession, document_id: str) -> Document:
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.ingestion_jobs))
        .where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found.", status_code=404)
    return document


def assert_document_access(current: CurrentUser, document: Document) -> None:
    if current.is_super_admin:
        return
    if document.department_id not in current.department_ids:
        raise AppError("DOCUMENT_ACCESS_DENIED", "You do not have access to this document.", status_code=403)


async def list_documents(
    db: AsyncSession,
    current: CurrentUser,
    *,
    status: str | None = None,
    department_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc())
    if status:
        stmt = stmt.where(Document.status == DocumentStatus(status))
    if current.is_super_admin:
        if department_id:
            stmt = stmt.where(Document.department_id == department_id)
    else:
        stmt = stmt.where(Document.department_id.in_(current.department_ids))
        if department_id and department_id in current.department_ids:
            stmt = stmt.where(Document.department_id == department_id)

    offset = max(page - 1, 0) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_document_upload(
    db: AsyncSession,
    current: CurrentUser,
    *,
    settings: Settings,
    filename: str,
    content: bytes,
    title: str | None,
    department_id: str | None,
) -> tuple[Document, IngestionJob]:
    if not filename.lower().endswith(".pdf"):
        raise AppError("INVALID_FILE_TYPE", "Only PDF files are supported.", status_code=400)
    if len(content) > settings.max_upload_bytes:
        raise AppError("FILE_TOO_LARGE", "File exceeds maximum allowed size.", status_code=400)

    if current.is_super_admin:
        resolved_department_id = department_id or (current.department_ids[0] if current.department_ids else None)
        if not resolved_department_id:
            raise AppError(
                "DEPARTMENT_NOT_FOUND",
                "Super Admin must specify a valid department_id from GET /api/v1/departments.",
                status_code=400,
            )
    else:
        if not current.department_ids:
            raise AppError("NOT_AUTHORIZED", "Admin has no assigned department.", status_code=403)
        if department_id and department_id not in current.department_ids:
            raise AppError("NOT_AUTHORIZED", "You cannot upload to this department.", status_code=403)
        resolved_department_id = department_id or current.department_ids[0]

    await get_department(db, resolved_department_id)

    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid.uuid4()}_{filename}"
    storage_path = upload_root / storage_name
    storage_path.write_bytes(content)

    document = Document(
        title=title or filename,
        filename=filename,
        storage_path=str(storage_path),
        status=DocumentStatus.QUEUED,
        department_id=resolved_department_id,
        owner_user_id=current.user_id,
        size_bytes=len(content),
    )
    db.add(document)
    await db.flush()

    job = IngestionJob(
        document_id=document.id,
        status=IngestionJobStatus.QUEUED,
        progress=0,
        current_step="Queued for ingestion",
    )
    db.add(job)
    await db.flush()
    return document, job


async def delete_document(db: AsyncSession, current: CurrentUser, document_id: str) -> None:
    from app.config import get_settings
    from app.services.ingestion_pipeline import delete_document_index

    document = await get_document(db, document_id)
    assert_document_access(current, document)
    if not current.can_upload():
        raise AppError("NOT_AUTHORIZED", "Only Super Admin and Admin can delete documents.", status_code=403)

    settings = get_settings()
    delete_document_index(document_id, settings)

    if os.path.exists(document.storage_path):
        os.remove(document.storage_path)
    await db.delete(document)


async def get_ingestion_job(db: AsyncSession, job_id: str) -> IngestionJob:
    result = await db.execute(
        select(IngestionJob).options(selectinload(IngestionJob.document)).where(IngestionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise AppError("DOCUMENT_NOT_FOUND", "Ingestion job not found.", status_code=404)
    return job


async def list_document_elements(db: AsyncSession, document_id: str) -> list[DocumentElementResponse]:
    result = await db.execute(select(DocumentElement).where(DocumentElement.document_id == document_id))
    elements = result.scalars().all()
    return [
        DocumentElementResponse(
            element_id=e.id,
            document_id=e.document_id,
            element_type=e.element_type.value,
            page=e.page,
            source_ref=e.source_ref,
            content=e.content,
        )
        for e in elements
    ]
