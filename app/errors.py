from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ExtractionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class InputValidationError(ExtractionError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, status_code=400, details=details)


class JobNotFoundError(ExtractionError):
    def __init__(self, job_id: str) -> None:
        super().__init__(
            "JOB_NOT_FOUND",
            f"Extraction job '{job_id}' was not found.",
            status_code=404,
            details={"job_id": job_id},
        )


class AssetNotFoundError(ExtractionError):
    def __init__(self, asset_path: str) -> None:
        super().__init__(
            "ASSET_NOT_FOUND",
            f"Asset '{asset_path}' was not found.",
            status_code=404,
            details={"asset_path": asset_path},
        )


class ResultNotReadyError(ExtractionError):
    def __init__(self, job_id: str, resource: str) -> None:
        super().__init__(
            "RESULT_NOT_READY",
            f"{resource} is not available for job '{job_id}'.",
            status_code=404,
            details={"job_id": job_id, "resource": resource},
        )


class QueueBackpressureError(ExtractionError):
    def __init__(self, *, inflight: int, max_inflight: int) -> None:
        super().__init__(
            "QUEUE_BACKPRESSURE",
            "The extraction queue is full. Retry the upload after in-flight jobs complete.",
            status_code=429,
            details={"inflight": inflight, "max_inflight": max_inflight},
        )


class BenchmarkNotEnabledError(ExtractionError):
    def __init__(
        self,
        *,
        force_extractor: str | None = None,
        compare_extractors: bool = False,
    ) -> None:
        details: dict[str, Any] = {}
        if force_extractor:
            details["force_extractor"] = force_extractor
        if compare_extractors:
            details["compare_extractors"] = True
        super().__init__(
            "BENCHMARK_NOT_ENABLED",
            "force_extractor and compare_extractors are benchmark-only options "
            "and are disabled for this deployment. Omit them for a normal "
            "extraction, or set EXTRACTION_BENCHMARK_ENABLED=true.",
            status_code=403,
            details=details,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ExtractionError)
    async def extraction_error_handler(
        _request: Request,
        exc: ExtractionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
