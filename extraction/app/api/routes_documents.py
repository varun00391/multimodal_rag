from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.api.deps import get_repo, storage
from app.core.config import get_settings
from app.core.exceptions import DocumentNotFoundError, ExtractionError
from app.ingestion.upload import ingest_pdf
from app.models.document import CanonicalDocument
from app.orchestration.pipeline import ExtractionPipeline
from app.workers.extraction_worker import schedule_inline

router = APIRouter()


def _canonical(document_id: str) -> CanonicalDocument:
    try:
        get_repo().get_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    paths = storage().document_paths(document_id)
    if not paths.document_json.exists():
        raise HTTPException(status_code=409, detail="Extraction has not produced a representation yet.")
    payload = json.loads(paths.document_json.read_text(encoding="utf-8"))
    return CanonicalDocument.model_validate(payload)


@router.post("/documents")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    data = await file.read()
    try:
        document, job = ingest_pdf(file.filename or "upload.pdf", data, get_repo())
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc

    settings = get_settings()
    if settings.worker_mode.lower() == "inline":
        schedule_inline(background_tasks, document.id, job.id)

    return {
        "document_id": document.id,
        "job_id": job.id,
        "status": job.status.value,
    }


@router.get("/documents/{document_id}")
def get_document(document_id: str):
    try:
        document = get_repo().get_document(document_id)
        job = get_repo().get_job_for_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return {
        "document": document.model_dump(),
        "job": job.model_dump(),
    }


@router.get("/documents/{document_id}/pages")
def get_pages(document_id: str):
    canonical = _canonical(document_id)
    return {
        "document_id": document_id,
        "pages": [
            {
                "page_number": page.page_number,
                "width": page.width,
                "height": page.height,
                "width_px": page.width_px,
                "height_px": page.height_px,
                "dpi": page.dpi,
                "image_path": page.image_path,
                "profile": page.profile.model_dump() if page.profile else None,
                "region_count": len(page.regions),
            }
            for page in canonical.pages
        ],
    }


@router.get("/documents/{document_id}/regions")
def get_regions(document_id: str):
    canonical = _canonical(document_id)
    regions = []
    for page in canonical.pages:
        for region in page.regions:
            regions.append(region.model_dump())
    return {"document_id": document_id, "regions": regions}


@router.get("/documents/{document_id}/tables")
def get_tables(document_id: str):
    canonical = _canonical(document_id)
    tables = []
    for page in canonical.pages:
        for region in page.regions:
            if region.element and region.element.content.get("table"):
                tables.append(
                    {
                        "region_id": region.id,
                        "page": region.page,
                        "bbox": region.bbox,
                        "table": region.element.content["table"],
                        "validation": region.element.validation.model_dump(),
                    }
                )
    return {"document_id": document_id, "tables": tables}


@router.get("/documents/{document_id}/figures")
def get_figures(document_id: str):
    canonical = _canonical(document_id)
    figures = []
    for page in canonical.pages:
        for region in page.regions:
            if region.element and region.element.content.get("figure"):
                figures.append(
                    {
                        "region_id": region.id,
                        "page": region.page,
                        "bbox": region.bbox,
                        "type": region.type,
                        "figure": region.element.content["figure"],
                        "chart": region.element.content.get("chart"),
                        "diagram": region.element.content.get("diagram"),
                    }
                )
    return {"document_id": document_id, "figures": figures}


@router.get("/documents/{document_id}/representation")
def get_representation(document_id: str):
    return _canonical(document_id).model_dump()


@router.get("/documents/{document_id}/review-items")
def get_review_items(document_id: str):
    try:
        get_repo().get_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    items = get_repo().list_review_items(document_id)
    return {"document_id": document_id, "items": [item.model_dump() for item in items]}


@router.get("/documents/{document_id}/markdown")
def get_markdown(document_id: str):
    paths = storage().document_paths(document_id)
    if not paths.document_md.exists():
        raise HTTPException(status_code=409, detail="Markdown has not been generated yet.")
    return {"document_id": document_id, "markdown": paths.document_md.read_text(encoding="utf-8")}
