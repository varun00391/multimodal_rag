from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from extraction.errors import ExtractionError
from extraction.intake import document_dir, intake_file
from extraction.jobs.store import JobStore
from extraction.settings import get_settings
from extraction.store import load_document, load_report, resolve_under

import uuid

router = APIRouter()


def job_store() -> JobStore:
    return JobStore(get_settings().jobs_db_path)


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
