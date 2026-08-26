from __future__ import annotations

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.entities import Document, DocumentElement, IngestionJob
from app.models.enums import DocumentStatus, ElementType, IngestionJobStatus

_sync_session_factory: sessionmaker[Session] | None = None


def _get_sync_session_factory() -> sessionmaker[Session]:
    global _sync_session_factory
    if _sync_session_factory is None:
        settings = get_settings()
        sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(sync_url, pool_pre_ping=True)
        _sync_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _sync_session_factory


def update_ingestion_job(
    job_id: str,
    *,
    status: IngestionJobStatus | None = None,
    progress: int | None = None,
    current_step: str | None = None,
    error_message: str | None = None,
) -> None:
    session = _get_sync_session_factory()()
    try:
        job = session.get(IngestionJob, job_id)
        if not job:
            return
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if current_step is not None:
            job.current_step = current_step
        if error_message is not None:
            job.error_message = error_message
        session.commit()
    finally:
        session.close()


def update_document_status(document_id: str, status: DocumentStatus) -> None:
    session = _get_sync_session_factory()()
    try:
        document = session.get(Document, document_id)
        if not document:
            return
        document.status = status
        session.commit()
    finally:
        session.close()


def persist_document_elements(document_id: str, parents: list[dict]) -> None:
    session = _get_sync_session_factory()()
    try:
        session.execute(delete(DocumentElement).where(DocumentElement.document_id == document_id))
        for parent in parents:
            modality = str(parent.get("modality") or "text")
            element_type = _modality_to_element_type(modality)
            page = parent.get("page_start")
            content = str(parent.get("content") or "").strip()
            if parent.get("vision"):
                vision = parent["vision"]
                vision_text = str(vision.get("description") or "").strip()
                if vision_text:
                    content = f"{content}\n\n{vision_text}".strip() if content else vision_text
            session.add(
                DocumentElement(
                    document_id=document_id,
                    element_type=element_type,
                    page=page,
                    source_ref=str(parent.get("id") or ""),
                    content=content or None,
                )
            )
        session.commit()
    finally:
        session.close()


def _modality_to_element_type(modality: str) -> ElementType:
    mapping = {
        "text": ElementType.TEXT,
        "table": ElementType.TABLE,
        "picture": ElementType.IMAGE,
        "graph": ElementType.GRAPH,
    }
    return mapping.get(modality, ElementType.OTHER)
