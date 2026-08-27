import asyncio
import logging
import time
from pathlib import Path

from app.config import Settings
from app.inspection.pdf_inspector import PdfInspector
from app.adapters.pymupdf_adapter import PyMuPDFAdapter
from app.models.canonical import DocumentSource
from app.models.inspection import DocumentInspection
from app.models.jobs import JobStatus
from app.services.document_builder import (
    build_document,
    build_scanned_page,
    resolve_page_range,
)
from app.services.job_service import JobService
from app.storage.reports import write_model_json
from app.storage.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class ExtractionService:
    """Runs inspection and forced PyMuPDF extraction (Phase 2 baseline)."""

    def __init__(
        self,
        job_service: JobService,
        settings: Settings,
        inspector: PdfInspector,
        pymupdf_adapter: PyMuPDFAdapter,
        workspace_manager: WorkspaceManager,
    ) -> None:
        self._job_service = job_service
        self._settings = settings
        self._inspector = inspector
        self._pymupdf_adapter = pymupdf_adapter
        self._workspace_manager = workspace_manager

    def schedule(self, job_id: str) -> None:
        asyncio.create_task(self._run(job_id))

    async def _run(self, job_id: str) -> None:
        started = time.perf_counter()
        try:
            await self._job_service.mark_status(job_id, JobStatus.VALIDATING_INPUT)
            job = await self._job_service.require_job_record(job_id)
            workspace = Path(job.workspace_path)
            pdf_path = Path(job.source_path)
            page_start, page_end = resolve_page_range(
                job.page_count,
                job.policy.page_start,
                job.policy.page_end,
            )

            await self._job_service.mark_status(job_id, JobStatus.INSPECTING)
            inspection = await asyncio.to_thread(
                self._inspector.inspect,
                pdf_path,
                document_id=job.document_id,
                page_start=page_start,
                page_end=page_end,
            )
            write_model_json(workspace / "inspection.json", inspection)

            await self._job_service.mark_status(job_id, JobStatus.EXTRACTING)
            pages = await self._extract_pages(
                pdf_path=pdf_path,
                inspection=inspection,
                force_extractor=job.policy.force_extractor,
            )

            document = build_document(
                schema_version=self._settings.extraction_schema_version,
                document_id=job.document_id,
                source=DocumentSource(
                    filename=job.original_filename,
                    sha256=job.sha256,
                    size_bytes=pdf_path.stat().st_size,
                ),
                inspection=inspection,
                pages=pages,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            write_model_json(workspace / "document.json", document)
            write_model_json(
                workspace / "extraction-report.json",
                self._build_report(job_id=job_id, inspection=inspection, document=document),
            )

            final_status = (
                JobStatus.COMPLETED_WITH_WARNINGS
                if document.status == "completed_with_warnings"
                else JobStatus.COMPLETED
            )
            await self._job_service.mark_status(job_id, final_status)
            logger.info("Job %s finished with status %s", job_id, final_status.value)
        except Exception:
            logger.exception("Background extraction failed for job %s", job_id)
            await self._job_service.mark_failed(
                job_id,
                error_code="EXTRACTION_FAILED",
                error_message="Background extraction processing failed unexpectedly.",
            )

    async def _extract_pages(
        self,
        *,
        pdf_path: Path,
        inspection: DocumentInspection,
        force_extractor: str | None,
    ):
        if force_extractor and force_extractor not in {self._pymupdf_adapter.name, "pymupdf"}:
            raise ValueError(f"Unsupported force_extractor '{force_extractor}' in Phase 2.")

        force_pymupdf = force_extractor in {self._pymupdf_adapter.name, "pymupdf"}
        extractable_pages = [
            page.page
            for page in inspection.pages
            if force_pymupdf or not page.probable_scan
        ]

        extracted_by_page = {}
        if extractable_pages:
            result = await self._pymupdf_adapter.extract(pdf_path, extractable_pages, tasks=[])
            extracted_by_page = {page.page: page for page in result.pages}

        final_pages = []
        for page_inspection in inspection.pages:
            if page_inspection.probable_scan and not force_pymupdf:
                final_pages.append(build_scanned_page(page_inspection))
            else:
                final_pages.append(extracted_by_page[page_inspection.page])
        return final_pages

    @staticmethod
    def _build_report(*, job_id: str, inspection: DocumentInspection, document) -> dict:
        return {
            "job_id": job_id,
            "schema_version": document.schema_version,
            "status": document.status,
            "inspection_summary": {
                "page_count": inspection.page_count,
                "scanned_pages": document.summary.scanned_pages,
                "pymupdf_fast_path_pages": [
                    page.page for page in inspection.pages if page.use_pymupdf_fast_path
                ],
            },
            "route_counts": document.summary.route_counts,
            "element_counts": document.summary.element_counts,
            "duration_ms": document.summary.duration_ms,
            "extractors": ["pymupdf"],
            "phase": "2-baseline",
        }
