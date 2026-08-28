import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import FormData

from app.config import Settings, get_settings
from app.errors import InputValidationError, QueueBackpressureError, ResultNotReadyError
from app.models.jobs import ExtractionPolicy, TERMINAL_JOB_STATUSES
from app.observability.metrics import get_metrics
from app.services.extraction_service import ExtractionService
from app.services.job_service import JobService
from app.storage.workspace import InputValidator, WorkspaceManager
from app.api.dependencies import (
    get_extraction_service,
    get_input_validator,
    get_job_service,
    get_workspace_manager,
)

router = APIRouter(prefix="/api/v1")


def _optional_form_str(form: FormData, key: str) -> str | None:
    value = form.get(key)
    return value if isinstance(value, str) else None


def _optional_form_bool(form: FormData, key: str, default: bool = False) -> bool:
    value = form.get(key)
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "on", "yes"}:
            return True
        if lowered in {"false", "0", "off", "no"}:
            return False
    return default


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics")
async def metrics() -> dict:
    return get_metrics().snapshot()


@router.post(
    "/extractions",
    status_code=status.HTTP_202_ACCEPTED,
    response_model_exclude_none=True,
)
async def create_extraction(
    request: Request,
    file: UploadFile = File(...),
    allow_managed_apis: bool = Form(default=True),
    visual_understanding: bool = Form(default=False),
    page_start: int | None = Form(default=None),
    page_end: int | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    input_validator: InputValidator = Depends(get_input_validator),
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager),
    job_service: JobService = Depends(get_job_service),
    extraction_service: ExtractionService = Depends(get_extraction_service),
) -> JSONResponse:
    """Upload a PDF and queue an extraction job.

    `force_extractor` and `compare_extractors` are accepted as extra form
    fields for authorized benchmark clients, but they are omitted from this
    form so `/docs` uploads are not rejected. They require
    `EXTRACTION_BENCHMARK_ENABLED=true`.
    """
    if not file.filename:
        raise InputValidationError("MISSING_FILENAME", "Uploaded file must include a filename.")

    form = await request.form()
    force_extractor = _optional_form_str(form, "force_extractor")
    compare_extractors = _optional_form_bool(form, "compare_extractors")

    content = await file.read()
    max_bytes = settings.extraction_max_file_bytes
    if len(content) > max_bytes:
        raise InputValidationError(
            "FILE_TOO_LARGE",
            f"Uploaded file exceeds the maximum size of {max_bytes} bytes.",
            details={"size_bytes": len(content), "max_bytes": max_bytes},
        )

    policy = JobService.validate_policy_options(
        ExtractionPolicy(
            allow_managed_apis=allow_managed_apis,
            visual_understanding=visual_understanding,
            page_start=page_start,
            page_end=page_end,
            force_extractor=force_extractor,
            compare_extractors=compare_extractors,
        ),
        benchmark_enabled=settings.extraction_benchmark_enabled,
        default_allow_managed_apis=settings.extraction_allow_managed_apis,
    )

    validation = input_validator.validate_upload_bytes(
        content,
        content_type=file.content_type,
        page_start=policy.page_start,
        page_end=policy.page_end,
    )

    workspace = workspace_manager.create_workspace(
        document_id=validation.sha256,
        pdf_bytes=content,
    )

    if not extraction_service.try_accept_job():
        inflight, max_inflight = extraction_service.queue_stats()
        raise QueueBackpressureError(inflight=inflight, max_inflight=max_inflight)

    try:
        response = await job_service.create_job(
            document_id=validation.sha256,
            original_filename=file.filename,
            source_path=str(workspace / "source.pdf"),
            workspace_path=str(workspace),
            sha256=validation.sha256,
            page_count=validation.page_count,
            policy=policy,
        )
    except Exception:
        extraction_service.release_accepted_job()
        raise
    extraction_service.schedule(response.job_id)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=response.model_dump(mode="json"),
    )


@router.get("/extractions/{job_id}")
async def get_extraction_status(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JSONResponse:
    job = await job_service.get_job(job_id)
    return JSONResponse(content=job.model_dump(mode="json"))


@router.get("/extractions/{job_id}/document")
async def get_extraction_document(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager),
) -> JSONResponse:
    job = await job_service.require_job_record(job_id)
    if job.status not in TERMINAL_JOB_STATUSES:
        raise ResultNotReadyError(job_id, "document.json")

    document_path = workspace_manager.document_json_path(Path(job.workspace_path))
    if not document_path.exists():
        raise ResultNotReadyError(job_id, "document.json")

    return JSONResponse(content=json.loads(document_path.read_text(encoding="utf-8")))


@router.get("/extractions/{job_id}/report")
async def get_extraction_report(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager),
) -> JSONResponse:
    job = await job_service.require_job_record(job_id)
    if job.status not in TERMINAL_JOB_STATUSES:
        raise ResultNotReadyError(job_id, "extraction-report.json")

    report_path = workspace_manager.report_json_path(Path(job.workspace_path))
    if not report_path.exists():
        raise ResultNotReadyError(job_id, "extraction-report.json")

    return JSONResponse(content=json.loads(report_path.read_text(encoding="utf-8")))


@router.get("/extractions/{job_id}/assets/{asset_path:path}")
async def get_extraction_asset(
    job_id: str,
    asset_path: str,
    job_service: JobService = Depends(get_job_service),
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager),
) -> FileResponse:
    job = await job_service.require_job_record(job_id)
    workspace = Path(job.workspace_path)
    asset_file = workspace_manager.asset_path(workspace, asset_path)
    if not asset_file.exists() or not asset_file.is_file():
        from app.errors import AssetNotFoundError

        raise AssetNotFoundError(asset_path)
    return FileResponse(asset_file)
