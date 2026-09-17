from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from extraction.errors import ExtractionError
from extraction.intake import document_dir, intake_file
from extraction.jobs.store import JobStore
from extraction.rag.service import ask_question, index_document
from extraction.settings import get_settings
from extraction.store import load_document, load_report, resolve_under

router = APIRouter()


def job_store() -> JobStore:
    return JobStore(get_settings().jobs_db_path)


def _http_error(exc: ExtractionError) -> HTTPException:
    status = {
        "JOB_NOT_FOUND": 404,
        "DOCUMENT_NOT_FOUND": 404,
        "JOB_NOT_READY": 409,
        "DOCUMENT_FAILED": 400,
        "NO_CHUNKS": 400,
        "EMPTY_QUESTION": 400,
        "QDRANT_NOT_CONFIGURED": 503,
        "QDRANT_UNAVAILABLE": 503,
        "EMBEDDINGS_UNAVAILABLE": 503,
        "EMBEDDINGS_UNAUTHORIZED": 401,
        "LLM_UNAVAILABLE": 503,
        "EMBEDDINGS_FAILED": 502,
        "LLM_EMPTY": 502,
    }.get(exc.code, 400)
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


class IndexRequest(BaseModel):
    job_id: str


class AskRequest(BaseModel):
    question: str
    job_id: str | None = Field(default=None)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/v1/extractions")
async def create_extraction(file: UploadFile = File(...)) -> dict:
    settings = get_settings()
    store = job_store()
    filename = file.filename or "upload"
    upload_dir = settings.workspace / "incoming"
    upload_dir.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())
    temp_path = upload_dir / f"{job_id}-{filename}"
    size = 0
    with temp_path.open("wb") as handle:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_upload_bytes:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="FILE_TOO_LARGE")
            handle.write(chunk)
    try:
        intake = intake_file(settings, temp_path, filename)
    except ExtractionError as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    finally:
        temp_path.unlink(missing_ok=True)
    record = store.create(job_id, intake.document_id, intake.filename)
    return {
        "job_id": record.job_id,
        "document_id": record.document_id,
        "status": record.status,
    }


@router.get("/api/v1/extractions/{job_id}")
def get_job(job_id: str) -> dict:
    record = job_store().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
    return record.model_dump()


@router.get("/api/v1/extractions/{job_id}/document")
def get_document(job_id: str) -> dict:
    record = job_store().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
    if record.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="JOB_NOT_READY")
    document = load_document(document_dir(get_settings(), record.document_id))
    if document is None:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
    return document.model_dump(mode="json")


@router.get("/api/v1/extractions/{job_id}/report")
def get_report(job_id: str) -> dict:
    record = job_store().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
    if record.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="JOB_NOT_READY")
    report = load_report(document_dir(get_settings(), record.document_id))
    if report is None:
        raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")
    return report.model_dump(mode="json")


@router.get("/api/v1/extractions/{job_id}/assets/{asset_path:path}")
def get_asset(job_id: str, asset_path: str):
    record = job_store().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
    root = document_dir(get_settings(), record.document_id)
    try:
        target = resolve_under(root / "assets", asset_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="INVALID_ASSET_PATH") from None
    if not target.is_file():
        raise HTTPException(status_code=404, detail="ASSET_NOT_FOUND")
    return FileResponse(target)


@router.post("/api/v1/index")
async def create_index(body: IndexRequest) -> dict:
    try:
        return await asyncio.to_thread(index_document, get_settings(), job_store(), body.job_id)
    except ExtractionError as exc:
        raise _http_error(exc) from exc


@router.post("/api/v1/ask")
async def create_ask(body: AskRequest) -> dict:
    try:
        return await asyncio.to_thread(ask_question, get_settings(), job_store(), body.question, body.job_id)
    except ExtractionError as exc:
        raise _http_error(exc) from exc
