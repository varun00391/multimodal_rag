from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from app.adapters.docling_adapter import DoclingAdapter
from app.adapters.gemini_adapter import GeminiAdapter
from app.adapters.groq_vision_adapter import GroqVisionAdapter
from app.adapters.pymupdf_adapter import PyMuPDFAdapter
from app.config import Settings
from app.execution.limits import ProviderCircuitBreaker, get_circuit_breaker
from app.models.canonical import CanonicalExtractionResult, ExtractionError
from app.models.routing import ExtractionGroup
from app.observability.logging import log_event
from app.observability.metrics import ExtractionMetrics, get_metrics
from app.storage.cache import ExtractionCache

logger = logging.getLogger(__name__)


@dataclass
class GroupRun:
    group: ExtractionGroup
    result: CanonicalExtractionResult | None = None
    error: ExtractionError | None = None
    cache_hit: bool = False
    duration_ms: int = 0
    circuit_open: bool = False


class ExtractionExecutor:
    def __init__(
        self,
        settings: Settings,
        pymupdf_adapter: PyMuPDFAdapter,
        docling_adapter: DoclingAdapter,
        gemini_adapter: GeminiAdapter | None = None,
        groq_adapter: GroqVisionAdapter | None = None,
        *,
        cache: ExtractionCache | None = None,
        circuit_breaker: ProviderCircuitBreaker | None = None,
        metrics: ExtractionMetrics | None = None,
    ) -> None:
        self._settings = settings
        self._adapters: dict[str, object] = {
            "pymupdf": pymupdf_adapter,
            "docling": docling_adapter,
        }
        if gemini_adapter is not None:
            self._adapters["gemini"] = gemini_adapter
        if groq_adapter is not None:
            self._adapters["groq-vision"] = groq_adapter
        self._semaphores = {
            "pymupdf": asyncio.Semaphore(max(1, settings.pymupdf_max_concurrency)),
            "docling": asyncio.Semaphore(max(1, settings.docling_max_concurrency)),
            "gemini": asyncio.Semaphore(max(1, settings.gemini_max_concurrency)),
            "groq-vision": asyncio.Semaphore(max(1, settings.groq_max_concurrency)),
        }
        self._timeout = max(1, settings.extraction_group_timeout_seconds)
        self._cache = cache if cache is not None else ExtractionCache(settings)
        self._circuit_breaker = circuit_breaker or get_circuit_breaker(settings)
        self._metrics = metrics if metrics is not None else get_metrics()

    async def run(self, pdf_path: Path, groups: list[ExtractionGroup]) -> list[GroupRun]:
        if not groups:
            return []
        return list(await asyncio.gather(*[self._run_group(pdf_path, group) for group in groups]))

    async def _run_group(self, pdf_path: Path, group: ExtractionGroup) -> GroupRun:
        started = time.perf_counter()
        cache_key = self._cache.group_key(group)
        cached = self._cache.get_group(cache_key)
        if cached is not None:
            self._metrics.record_cache(hit=True)
            self._metrics.record_extractor(group.extractor, success=True)
            duration_ms = int((time.perf_counter() - started) * 1000)
            log_event(
                logger,
                "extraction_group_cache_hit",
                group_id=group.group_id,
                extractor=group.extractor,
                pages=group.pages,
                duration_ms=duration_ms,
            )
            return GroupRun(group=group, result=cached, cache_hit=True, duration_ms=duration_ms)

        self._metrics.record_cache(hit=False)

        adapter = self._adapters.get(group.extractor)
        if adapter is None or not hasattr(adapter, "extract"):
            return GroupRun(
                group=group,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=ExtractionError(
                    code="EXTRACTOR_NOT_AVAILABLE",
                    message=f"No adapter is available for extractor '{group.extractor}'.",
                    details={"group_id": group.group_id, "extractor": group.extractor},
                ),
            )

        semaphore = self._semaphores.get(group.extractor, asyncio.Semaphore(1))
        try:
            async with semaphore:
                if not self._circuit_breaker.allow(group.extractor):
                    self._metrics.record_circuit_open()
                    log_event(
                        logger,
                        "extraction_group_circuit_open",
                        group_id=group.group_id,
                        extractor=group.extractor,
                        pages=group.pages,
                    )
                    return GroupRun(
                        group=group,
                        circuit_open=True,
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        error=ExtractionError(
                            code="PROVIDER_CIRCUIT_OPEN",
                            message=(
                                f"Managed extractor '{group.extractor}' is temporarily unavailable "
                                "because its circuit breaker is open."
                            ),
                            details={
                                "group_id": group.group_id,
                                "extractor": group.extractor,
                                "pages": group.pages,
                            },
                        ),
                    )
                result = await asyncio.wait_for(
                    adapter.extract(
                        pdf_path,
                        list(group.pages),
                        list(group.tasks),
                        context_pages=list(group.context_pages) or None,
                    ),
                    timeout=self._timeout,
                )
            self._circuit_breaker.record_success(group.extractor)
            self._metrics.record_extractor(group.extractor, success=True)
            self._cache.put_group(cache_key, result)
            duration_ms = int((time.perf_counter() - started) * 1000)
            for _page in result.pages:
                self._metrics.record_page_latency(duration_ms)
            log_event(
                logger,
                "extraction_group_completed",
                group_id=group.group_id,
                extractor=group.extractor,
                pages=group.pages,
                duration_ms=duration_ms,
                element_count=sum(len(page.elements) for page in result.pages),
            )
            return GroupRun(group=group, result=result, duration_ms=duration_ms)
        except asyncio.TimeoutError:
            self._circuit_breaker.record_failure(group.extractor)
            self._metrics.record_extractor(group.extractor, success=False)
            logger.warning("Extraction group %s timed out", group.group_id)
            return GroupRun(
                group=group,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=ExtractionError(
                    code="EXTRACTION_GROUP_TIMEOUT",
                    message=f"Extraction group '{group.group_id}' timed out.",
                    details={
                        "group_id": group.group_id,
                        "extractor": group.extractor,
                        "pages": group.pages,
                    },
                ),
            )
        except Exception as exc:
            self._circuit_breaker.record_failure(group.extractor)
            self._metrics.record_extractor(group.extractor, success=False)
            log_event(
                logger,
                "extraction_group_failed",
                group_id=group.group_id,
                extractor=group.extractor,
                pages=group.pages,
                error_type=type(exc).__name__,
            )
            logger.exception("Extraction group %s failed", group.group_id)
            return GroupRun(
                group=group,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=_group_error(group, exc),
            )


def _group_error(group: ExtractionGroup, exc: Exception) -> ExtractionError:
    code = {
        "pymupdf": "PYMUPDF_EXTRACTION_FAILED",
        "docling": "DOCLING_EXTRACTION_FAILED",
        "gemini": "GEMINI_EXTRACTION_FAILED",
        "groq-vision": "GROQ_EXTRACTION_FAILED",
    }.get(group.extractor, "EXTRACTION_GROUP_FAILED")
    return ExtractionError(
        code=code,
        message=str(exc),
        details={
            "group_id": group.group_id,
            "extractor": group.extractor,
            "profile": group.profile,
            "pages": group.pages,
        },
    )
