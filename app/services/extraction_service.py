import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.adapters.docling_adapter import DoclingAdapter
from app.adapters.gemini_adapter import GeminiAdapter
from app.adapters.groq_vision_adapter import GroqVisionAdapter
from app.adapters.pymupdf_adapter import PyMuPDFAdapter
from app.config import Settings
from app.execution.executor import ExtractionExecutor
from app.execution.limits import JobLimiter, ProviderCircuitBreaker, get_circuit_breaker, get_job_limiter
from app.fallback.manager import FallbackManager, FallbackRecord
from app.grouping.planner import GroupPlanner
from app.inspection.pdf_inspector import PdfInspector
from app.merge.combiner import combine_pages
from app.merge.merger import finalize_pages
from app.models.canonical import DocumentSource
from app.models.inspection import DocumentInspection
from app.models.jobs import ExtractionPolicy, JobStatus
from app.models.routing import ExtractionGroup, PagePlan
from app.observability.logging import log_event
from app.observability.metrics import ExtractionMetrics, get_metrics
from app.routing.policy import RoutingPolicy, SUPPORTED_FORCE_EXTRACTORS
from app.services.document_builder import build_document, resolve_page_range
from app.services.job_service import JobService
from app.storage.cache import ExtractionCache
from app.storage.reports import write_model_json
from app.storage.workspace import WorkspaceManager
from app.validation.validator import PageValidator

logger = logging.getLogger(__name__)

__all__ = ["ExtractionService", "ExtractionOutcome", "SUPPORTED_FORCE_EXTRACTORS"]


@dataclass
class ExtractionOutcome:
    pages: list
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    gemini_finish_reasons: list[str] = field(default_factory=list)
    validations: list = field(default_factory=list)
    plans: list[PagePlan] = field(default_factory=list)
    groups: list[ExtractionGroup] = field(default_factory=list)
    fallbacks: list[FallbackRecord] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    circuit_open: int = 0
    group_durations_ms: list[int] = field(default_factory=list)


class ExtractionService:
    """Runs inspection, routing, grouped extraction, and page validation."""

    def __init__(
        self,
        job_service: JobService,
        settings: Settings,
        inspector: PdfInspector,
        pymupdf_adapter: PyMuPDFAdapter,
        docling_adapter: DoclingAdapter,
        workspace_manager: WorkspaceManager,
        gemini_adapter: GeminiAdapter | None = None,
        groq_adapter: GroqVisionAdapter | None = None,
        validator: PageValidator | None = None,
        router: RoutingPolicy | None = None,
        grouper: GroupPlanner | None = None,
        executor: ExtractionExecutor | None = None,
        fallback_manager: FallbackManager | None = None,
        cache: ExtractionCache | None = None,
        circuit_breaker: ProviderCircuitBreaker | None = None,
        metrics: ExtractionMetrics | None = None,
        limiter: JobLimiter | None = None,
    ) -> None:
        self._job_service = job_service
        self._settings = settings
        self._inspector = inspector
        self._pymupdf_adapter = pymupdf_adapter
        self._docling_adapter = docling_adapter
        self._gemini_adapter = gemini_adapter
        self._groq_adapter = groq_adapter
        self._workspace_manager = workspace_manager
        self._validator = validator or PageValidator(settings)
        self._router = router or RoutingPolicy(settings)
        self._grouper = grouper or GroupPlanner(settings)
        self._cache = cache if cache is not None else ExtractionCache(settings)
        self._circuit_breaker = circuit_breaker or get_circuit_breaker(settings)
        self._metrics = metrics if metrics is not None else get_metrics()
        self._limiter = limiter or get_job_limiter(settings)
        self._executor = executor or ExtractionExecutor(
            settings,
            pymupdf_adapter,
            docling_adapter,
            gemini_adapter,
            groq_adapter,
            cache=self._cache,
            circuit_breaker=self._circuit_breaker,
            metrics=self._metrics,
        )
        self._fallback_manager = fallback_manager or FallbackManager(
            settings,
            self._executor,
            self._validator,
        )

    def try_accept_job(self) -> bool:
        return self._limiter.try_accept()

    def release_accepted_job(self) -> None:
        self._limiter.release_accepted()

    def queue_stats(self) -> tuple[int, int]:
        return self._limiter.inflight, self._limiter.max_inflight

    def schedule(self, job_id: str) -> None:
        asyncio.create_task(self._guarded_run(job_id))

    async def _guarded_run(self, job_id: str) -> None:
        try:
            async with self._limiter.slot():
                await self._run(job_id)
        finally:
            self._limiter.release_accepted()

    async def _run(self, job_id: str) -> None:
        started = time.perf_counter()
        timings: dict[str, int] = {}
        cache_hit = False
        self._metrics.record_job_started()
        log_event(logger, "extraction_job_started", job_id=job_id)
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

            document_key = self._cache.document_key(sha256=job.sha256, policy=job.policy)
            cached_document = self._cache.get_document(document_key)
            if cached_document is not None:
                cache_hit = True
                self._metrics.record_cache(hit=True)
                duration_ms = int((time.perf_counter() - started) * 1000)
                restored = self._restore_cached_document(
                    job_id=job_id,
                    workspace=workspace,
                    cached=cached_document,
                    duration_ms=duration_ms,
                )
                await self._job_service.mark_complete(
                    job_id,
                    JobStatus(restored["status"])
                    if restored["status"] in {item.value for item in JobStatus}
                    else JobStatus.COMPLETED,
                    duration_ms=duration_ms,
                    cache_hit=True,
                    document_path=str(workspace / "document.json"),
                    report_path=str(workspace / "extraction-report.json"),
                )
                self._metrics.record_job_completed(
                    duration_ms=duration_ms,
                    cost_usd=float(
                        ((restored.get("document") or {}).get("summary") or {}).get("estimated_cost_usd") or 0.0
                    ),
                    cache_hit=True,
                    failed=False,
                )
                log_event(
                    logger,
                    "extraction_job_cache_hit",
                    job_id=job_id,
                    document_id=job.document_id,
                    duration_ms=duration_ms,
                )
                return

            self._metrics.record_cache(hit=False)

            await self._job_service.mark_status(job_id, JobStatus.INSPECTING)
            inspect_started = time.perf_counter()
            inspection_key = self._cache.inspection_key(
                sha256=job.sha256,
                page_start=page_start,
                page_end=page_end,
            )
            inspection = self._cache.get_inspection(inspection_key)
            inspection_cache_hit = inspection is not None
            if inspection is None:
                inspection = await asyncio.to_thread(
                    self._inspector.inspect,
                    pdf_path,
                    document_id=job.document_id,
                    page_start=page_start,
                    page_end=page_end,
                )
                self._cache.put_inspection(inspection_key, inspection)
            write_model_json(workspace / "inspection.json", inspection)
            timings["inspect_ms"] = int((time.perf_counter() - inspect_started) * 1000)

            await self._job_service.mark_status(job_id, JobStatus.PLANNING)
            plan_started = time.perf_counter()
            plans, groups = self._plan(
                inspection,
                job.policy,
                document_id=job.document_id,
            )
            routing_payload = {
                "plans": [plan.model_dump(mode="json") for plan in plans],
                "groups": [group.model_dump(mode="json") for group in groups],
            }
            write_model_json(workspace / "routing.json", routing_payload)
            timings["plan_ms"] = int((time.perf_counter() - plan_started) * 1000)

            await self._job_service.mark_status(job_id, JobStatus.EXTRACTING)
            extract_started = time.perf_counter()
            outcome = await self._execute(
                pdf_path=pdf_path,
                inspection=inspection,
                plans=plans,
                groups=groups,
            )
            timings["extract_ms"] = int((time.perf_counter() - extract_started) * 1000)
            if inspection_cache_hit:
                outcome.cache_hits += 1
            else:
                outcome.cache_misses += 1

            await self._job_service.mark_status(job_id, JobStatus.VALIDATING_OUTPUT)
            validate_started = time.perf_counter()
            outcome.validations = self._validator.validate_pages(
                outcome.pages,
                inspection,
                workspace=workspace,
            )
            timings["validate_ms"] = int((time.perf_counter() - validate_started) * 1000)

            if not job.policy.force_extractor:
                await self._job_service.mark_status(job_id, JobStatus.RETRYING)
                fallback_started = time.perf_counter()
                resolution = await self._fallback_manager.resolve(
                    pdf_path,
                    outcome.pages,
                    outcome.validations,
                    inspection,
                    job.policy,
                    document_id=job.document_id,
                    gemini_ready=bool(self._gemini_adapter and self._gemini_adapter.is_configured),
                    groq_ready=self._groq_ready(),
                    workspace=workspace,
                )
                outcome.pages = resolution.pages
                outcome.fallbacks = resolution.records
                outcome.prompt_tokens += resolution.prompt_tokens
                outcome.completion_tokens += resolution.completion_tokens
                outcome.estimated_cost_usd += resolution.estimated_cost_usd
                outcome.gemini_finish_reasons.extend(resolution.gemini_finish_reasons)
                if resolution.validations:
                    outcome.validations = resolution.validations
                for _record in resolution.records:
                    self._metrics.record_fallback()
                timings["fallback_ms"] = int((time.perf_counter() - fallback_started) * 1000)
            else:
                timings["fallback_ms"] = 0

            await self._job_service.mark_status(job_id, JobStatus.MERGING)
            merge_started = time.perf_counter()
            outcome.pages = finalize_pages(outcome.pages, inspection)
            outcome.validations = self._validator.validate_pages(
                outcome.pages,
                inspection,
                workspace=workspace,
            )
            timings["merge_ms"] = int((time.perf_counter() - merge_started) * 1000)

            duration_ms = int((time.perf_counter() - started) * 1000)
            timings["total_ms"] = duration_ms
            document = build_document(
                schema_version=self._settings.extraction_schema_version,
                document_id=job.document_id,
                source=DocumentSource(
                    filename=job.original_filename,
                    sha256=job.sha256,
                    size_bytes=pdf_path.stat().st_size,
                ),
                inspection=inspection,
                pages=outcome.pages,
                duration_ms=duration_ms,
                estimated_cost_usd=outcome.estimated_cost_usd,
            )
            report = self._build_report(
                job_id=job_id,
                inspection=inspection,
                document=document,
                force_extractor=job.policy.force_extractor,
                allow_managed_apis=job.policy.allow_managed_apis,
                outcome=outcome,
                min_validation_confidence=self._settings.extraction_min_validation_confidence,
                timings=timings,
                cache_hit=False,
                inspection_cache_hit=inspection_cache_hit,
            )
            write_model_json(workspace / "document.json", document)
            write_model_json(workspace / "extraction-report.json", report)
            if document.status != "failed":
                self._cache.put_document(
                    document_key,
                    document=document.model_dump(mode="json"),
                    report=report,
                    inspection=inspection.model_dump(mode="json"),
                    routing=routing_payload,
                    status=document.status,
                )

            final_status = (
                JobStatus.COMPLETED_WITH_WARNINGS
                if document.status == "completed_with_warnings"
                else JobStatus.COMPLETED
            )
            await self._job_service.mark_complete(
                job_id,
                final_status,
                duration_ms=duration_ms,
                cache_hit=False,
                document_path=str(workspace / "document.json"),
                report_path=str(workspace / "extraction-report.json"),
            )
            self._metrics.record_job_completed(
                duration_ms=duration_ms,
                cost_usd=document.summary.estimated_cost_usd,
                cache_hit=False,
                failed=False,
            )
            log_event(
                logger,
                "extraction_job_completed",
                job_id=job_id,
                document_id=job.document_id,
                status=final_status.value,
                duration_ms=duration_ms,
                cache_hits=outcome.cache_hits,
                fallbacks=len(outcome.fallbacks),
            )
        except Exception:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception("Background extraction failed for job %s", job_id)
            log_event(
                logger,
                "extraction_job_failed",
                job_id=job_id,
                duration_ms=duration_ms,
                cache_hit=cache_hit,
            )
            self._metrics.record_job_completed(
                duration_ms=duration_ms,
                cost_usd=0.0,
                cache_hit=cache_hit,
                failed=True,
            )
            await self._job_service.mark_failed(
                job_id,
                error_code="EXTRACTION_FAILED",
                error_message="Background extraction processing failed unexpectedly.",
                duration_ms=duration_ms,
            )

    def _restore_cached_document(
        self,
        *,
        job_id: str,
        workspace: Path,
        cached: dict[str, Any],
        duration_ms: int,
    ) -> dict[str, Any]:
        document = dict(cached["document"])
        report = dict(cached["report"])
        report["job_id"] = job_id
        report["cache"] = {
            **(report.get("cache") or {}),
            "hit": True,
            "document_hit": True,
        }
        report["duration_ms"] = duration_ms
        report["phase"] = "9-reporting-cache-hardening"
        status = cached.get("status") or document.get("status") or "completed"
        write_model_json(workspace / "document.json", document)
        write_model_json(workspace / "extraction-report.json", report)
        write_model_json(workspace / "inspection.json", cached["inspection"])
        if cached.get("routing"):
            write_model_json(workspace / "routing.json", cached["routing"])
        return {"status": status, "document": document, "report": report}

    def _plan(
        self,
        inspection: DocumentInspection,
        policy: ExtractionPolicy,
        *,
        document_id: str,
    ) -> tuple[list[PagePlan], list[ExtractionGroup]]:
        gemini_ready = bool(self._gemini_adapter and self._gemini_adapter.is_configured)
        plans = self._router.create_plans(
            inspection,
            policy,
            document_id=document_id,
            gemini_ready=gemini_ready,
            groq_ready=self._groq_configured(),
        )
        groups = self._grouper.create_groups(
            plans,
            document_id=document_id,
            inspection=inspection,
        )
        return plans, groups

    async def _extract_pages(
        self,
        *,
        pdf_path: Path,
        inspection: DocumentInspection,
        force_extractor: str | None,
        allow_managed_apis: bool,
        visual_understanding: bool = False,
    ) -> ExtractionOutcome:
        policy = ExtractionPolicy(
            force_extractor=force_extractor,
            allow_managed_apis=allow_managed_apis,
            visual_understanding=visual_understanding,
        )
        plans, groups = self._plan(
            inspection,
            policy,
            document_id=inspection.document_id,
        )
        return await self._execute(
            pdf_path=pdf_path,
            inspection=inspection,
            plans=plans,
            groups=groups,
        )

    async def _execute(
        self,
        *,
        pdf_path: Path,
        inspection: DocumentInspection,
        plans: list[PagePlan],
        groups: list[ExtractionGroup],
    ) -> ExtractionOutcome:
        runs = await self._executor.run(pdf_path, groups)
        pages = finalize_pages(combine_pages(inspection, plans, runs), inspection)
        prompt_tokens = 0
        completion_tokens = 0
        estimated_cost_usd = 0.0
        finish_reasons: list[str] = []
        cache_hits = 0
        cache_misses = 0
        circuit_open = 0
        durations: list[int] = []
        for run in runs:
            durations.append(run.duration_ms)
            if run.cache_hit:
                cache_hits += 1
            else:
                cache_misses += 1
            if run.circuit_open:
                circuit_open += 1
            if run.result is None:
                continue
            usage = run.result.metadata.get("usage") or {}
            prompt_tokens += int(usage.get("prompt_tokens") or 0)
            completion_tokens += int(usage.get("completion_tokens") or 0)
            estimated_cost_usd += float(usage.get("estimated_cost_usd") or 0.0)
            finish_reasons.extend(str(item) for item in (usage.get("finish_reasons") or []) if item)
            if usage.get("finish_reason"):
                finish_reasons.append(str(usage["finish_reason"]))
        return ExtractionOutcome(
            pages=pages,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=estimated_cost_usd,
            gemini_finish_reasons=finish_reasons,
            plans=plans,
            groups=groups,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            circuit_open=circuit_open,
            group_durations_ms=durations,
        )

    def _build_report(
        self,
        *,
        job_id: str,
        inspection: DocumentInspection,
        document,
        force_extractor: str | None,
        allow_managed_apis: bool,
        outcome: ExtractionOutcome | None = None,
        min_validation_confidence: float = 0.85,
        timings: dict[str, int] | None = None,
        cache_hit: bool = False,
        inspection_cache_hit: bool = False,
    ) -> dict:
        extractors = sorted(
            {route for page in document.pages for route in page.extraction_routes if route}
        )
        profiles = sorted(
            {
                attempt.profile
                for page in document.pages
                for attempt in page.attempts
                if attempt.profile
            }
        )
        usage = {
            "prompt_tokens": outcome.prompt_tokens if outcome else 0,
            "completion_tokens": outcome.completion_tokens if outcome else 0,
            "total_tokens": (
                (outcome.prompt_tokens + outcome.completion_tokens) if outcome else 0
            ),
            "estimated_cost_usd": document.summary.estimated_cost_usd,
            "finish_reasons": outcome.gemini_finish_reasons if outcome else [],
        }
        validations = list(outcome.validations) if outcome else []
        plans = list(outcome.plans) if outcome else []
        groups = list(outcome.groups) if outcome else []
        fallbacks = list(outcome.fallbacks) if outcome else []
        validation_by_page = {item.page: item for item in validations}
        plan_by_page = {plan.page: plan for plan in plans}
        pages_report = []
        for page in document.pages:
            validation = validation_by_page.get(page.page)
            plan = plan_by_page.get(page.page)
            pages_report.append(
                {
                    "page": page.page,
                    "primary_route": page.primary_route,
                    "routing_reasons": page.routing_reasons,
                    "routing_confidence": page.routing_confidence,
                    "extraction_routes": page.extraction_routes,
                    "element_count": len(page.elements),
                    "attempt_count": len(page.attempts),
                    "validation_passed": None if validation is None else validation.passed,
                    "validation_confidence": None if validation is None else validation.confidence,
                    "task_kinds": [task.kind for task in plan.tasks] if plan else [],
                    "overall_confidence": page.overall_confidence,
                    "status": "failed" if page.errors and not page.elements else "ok",
                }
            )
        cache_hits = outcome.cache_hits if outcome else 0
        cache_misses = outcome.cache_misses if outcome else 0
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
            "durations": timings or {"total_ms": document.summary.duration_ms},
            "extractors": extractors or ["pymupdf"],
            "profiles": profiles,
            "force_extractor": force_extractor,
            "allow_managed_apis": allow_managed_apis,
            "phase": _report_phase(force_extractor, extractors),
            "gemini_provider": "euron" if "gemini" in extractors else None,
            "versions": self._cache.versions(),
            "usage": usage,
            "cache": {
                "enabled": self._cache.enabled,
                "hit": cache_hit,
                "document_hit": cache_hit,
                "inspection_hit": inspection_cache_hit,
                "group_hits": cache_hits,
                "group_misses": cache_misses,
            },
            "circuit_breakers": self._circuit_breaker.snapshot(),
            "metrics": self._metrics.snapshot(),
            "routing": {
                "plans": [plan.model_dump(mode="json") for plan in plans],
                "groups": [
                    {
                        "group_id": group.group_id,
                        "extractor": group.extractor,
                        "profile": group.profile,
                        "kind": group.kind,
                        "pages": group.pages,
                        "context_pages": group.context_pages,
                    }
                    for group in groups
                ],
            },
            "fallbacks": [
                {
                    "page": record.page,
                    "reason_code": record.reason_code,
                    "from_extractor": record.from_extractor,
                    "to_extractor": record.to_extractor,
                    "to_profile": record.to_profile,
                    "status": record.status,
                    "message": record.message,
                }
                for record in fallbacks
            ],
            "pages": pages_report,
            "validation": {
                "min_confidence": min_validation_confidence,
                "page_count": len(validations),
                "failed_pages": [item.page for item in validations if not item.passed],
                "pages": [item.model_dump(mode="json") for item in validations],
            },
        }

    def _groq_configured(self) -> bool:
        return bool(self._groq_adapter and self._groq_adapter.is_configured)

    def _groq_ready(self) -> bool:
        return bool(self._settings.groq_visual_extraction_enabled and self._groq_configured())


def _report_phase(force_extractor: str | None, extractors: list[str] | None = None) -> str:
    if force_extractor == "groq-vision":
        return "8-groq-vision"
    if force_extractor == "gemini":
        return "4-gemini-baseline"
    if force_extractor and force_extractor.startswith("docling"):
        return "3-docling-baseline"
    if force_extractor == "pymupdf":
        return "2-pymupdf-baseline"
    if extractors and "groq-vision" in extractors:
        return "8-groq-vision"
    return "9-reporting-cache-hardening"
