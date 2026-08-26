from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.deps import CurrentUser, get_current_user, require_upload_permission
from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.api import (
    DocumentElementResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.audit import write_audit_log
from app.services.documents import (
    assert_document_access,
    create_document_upload,
    delete_document,
    get_document,
    list_document_elements,
    list_documents,
)
from app.services.ingestion_worker import schedule_ingestion_job

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    department_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_upload_permission),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadResponse:
    content = await file.read()
    document, job = await create_document_upload(
        db,
        current,
        settings=settings,
        filename=file.filename or "upload.pdf",
        content=content,
        title=title,
        department_id=department_id,
    )
    await write_audit_log(
        db,
        event_type="DOCUMENT_UPLOADED",
        actor_user_id=current.user_id,
        resource_type="document",
        resource_id=document.id,
        details={"filename": document.filename, "department_id": document.department_id},
    )
    await db.commit()
    await schedule_ingestion_job(
        job_id=job.id,
        document_id=document.id,
        storage_path=document.storage_path,
    )
    return DocumentUploadResponse(
        document_id=document.id,
        status=document.status.value,
        ingestion_job_id=job.id,
    )


@router.get("", response_model=list[DocumentResponse])
async def get_documents(
    status: str | None = None,
    department_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[DocumentResponse]:
    docs = await list_documents(
        db,
        current,
        status=status,
        department_id=department_id,
        page=page,
        page_size=page_size,
    )
    return [
        DocumentResponse(
            document_id=d.id,
            title=d.title,
            filename=d.filename,
            status=d.status.value,
            department_id=d.department_id,
            owner_user_id=d.owner_user_id,
            size_bytes=d.size_bytes,
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_metadata(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> DocumentResponse:
    document = await get_document(db, document_id)
    assert_document_access(current, document)
    return DocumentResponse(
        document_id=document.id,
        title=document.title,
        filename=document.filename,
        status=document.status.value,
        department_id=document.department_id,
        owner_user_id=document.owner_user_id,
        size_bytes=document.size_bytes,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document_endpoint(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_upload_permission),
) -> None:
    await delete_document(db, current, document_id)
    await write_audit_log(
        db,
        event_type="DOCUMENT_DELETED",
        actor_user_id=current.user_id,
        resource_type="document",
        resource_id=document_id,
    )
    await db.commit()


@router.get("/{document_id}/elements", response_model=list[DocumentElementResponse])
async def get_document_elements(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[DocumentElementResponse]:
    document = await get_document(db, document_id)
    assert_document_access(current, document)
    return await list_document_elements(db, document_id)


@router.get("/{document_id}/elements/{element_id}", response_model=DocumentElementResponse)
async def get_document_element(
    document_id: str,
    element_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> DocumentElementResponse:
    document = await get_document(db, document_id)
    assert_document_access(current, document)
    elements = await list_document_elements(db, document_id)
    element = next((e for e in elements if e.element_id == element_id), None)
    if not element:
        raise AppError("DOCUMENT_NOT_FOUND", "Element not found.", status_code=404)
    return element
