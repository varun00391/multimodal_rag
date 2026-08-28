from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.adapters.euri_client import EuronGeminiClient, GeminiCompleter, GeminiCompletion
from app.adapters.gemini_pages import (
    RenderedPage,
    bbox_to_pdf_points,
    consecutive_groups,
    persist_rendered_pages,
    render_pages,
)
from app.adapters.gemini_prompt import PROMPT_VERSION, SYSTEM_PROMPT, user_prompt
from app.adapters.gemini_schema import GeminiElement, parse_gemini_payload
from app.config import Settings
from app.models.canonical import (
    CanonicalElement,
    CanonicalExtractionResult,
    CanonicalPage,
    ElementProvenance,
    ElementType,
    ExtractionAttempt,
    ExtractionError,
    ExtractorProvenance,
)
from app.models.routing import ExtractionTask

logger = logging.getLogger(__name__)

ADAPTER_VERSION = "1.0.0"


def estimate_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    *,
    input_usd_per_million: float,
    output_usd_per_million: float,
) -> float:
    return round(
        (prompt_tokens / 1_000_000) * input_usd_per_million
        + (completion_tokens / 1_000_000) * output_usd_per_million,
        6,
    )


class GeminiAdapter:
    name = "gemini"

    def __init__(
        self,
        settings: Settings,
        *,
        completer: GeminiCompleter | None = None,
    ) -> None:
        self._settings = settings
        self._completer = completer
        self._semaphore = asyncio.Semaphore(max(1, settings.gemini_max_concurrency))

    @property
    def is_configured(self) -> bool:
        return self._completer is not None or bool(self._settings.euri_api_key)

    def _require_completer(self) -> GeminiCompleter:
        if self._completer is not None:
            return self._completer
        if not self._settings.euri_api_key:
            raise RuntimeError("EURI_API_KEY is required to call Gemini through Euron.")
        self._completer = EuronGeminiClient(self._settings)
        return self._completer

    async def extract(
        self,
        pdf_path: Path,
        pages: list[int],
        tasks: list[ExtractionTask],
        context_pages: list[int] | None = None,
    ) -> CanonicalExtractionResult:
        requested = list(pages)
        extras = [page for page in (context_pages or []) if page not in requested]
        extract_pages = requested + extras
        started = time.perf_counter()
        if not requested:
            return CanonicalExtractionResult(pages=[], attempts=[], duration_ms=0)

        groups = consecutive_groups(
            extract_pages,
            target=self._settings.gemini_target_pages_per_group,
            max_size=self._settings.gemini_max_pages_per_group,
        )
        group_results = await asyncio.gather(
            *[self._extract_group(pdf_path, group) for group in groups]
        )

        pages_by_number: dict[int, CanonicalPage] = {}
        attempts: list[ExtractionAttempt] = []
        warnings: list[str] = []
        errors: list[ExtractionError] = []
        metadata: dict[str, Any] = {
            "provider": "euron",
            "base_url": self._settings.euri_base_url,
            "model": self._settings.gemini_model_id,
            "prompt_version": self._settings.gemini_extraction_prompt_version or PROMPT_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "groups": groups,
        }
        prompt_tokens = 0
        completion_tokens = 0
        finish_reasons: list[str] = []
        estimated_cost_usd = 0.0
        page_assets: list[str] = []

        for result in group_results:
            attempts.extend(result.attempts)
            warnings.extend(result.warnings)
            errors.extend(result.errors)
            for page in result.pages:
                pages_by_number[page.page] = page
            usage = result.metadata.get("usage") or {}
            prompt_tokens += int(usage.get("prompt_tokens") or 0)
            completion_tokens += int(usage.get("completion_tokens") or 0)
            estimated_cost_usd += float(usage.get("estimated_cost_usd") or 0.0)
            if usage.get("finish_reason"):
                finish_reasons.append(str(usage["finish_reason"]))
            page_assets.extend(result.metadata.get("page_assets") or [])

        duration_ms = int((time.perf_counter() - started) * 1000)
        metadata["usage"] = {
            "prompt_tokens": prompt_tokens or None,
            "completion_tokens": completion_tokens or None,
            "total_tokens": (prompt_tokens + completion_tokens) or None,
            "estimated_cost_usd": estimated_cost_usd,
            "finish_reasons": finish_reasons,
        }
        metadata["page_assets"] = page_assets
        ordered_pages = [
            pages_by_number[page_number]
            for page_number in requested
            if page_number in pages_by_number
        ]
        return CanonicalExtractionResult(
            pages=ordered_pages,
            attempts=attempts,
            warnings=warnings,
            errors=errors,
            duration_ms=duration_ms,
            metadata=metadata,
        )

    async def _extract_group(
        self,
        pdf_path: Path,
        pages: list[int],
    ) -> CanonicalExtractionResult:
        started = time.perf_counter()
        rendered = await asyncio.to_thread(
            render_pages,
            pdf_path,
            pages,
            max_pixels=self._settings.extraction_max_rendered_pixels,
        )
        page_assets = persist_rendered_pages(pdf_path, rendered)
        max_attempts = max(1, self._settings.extraction_max_attempts_per_page)
        if self._settings.gemini_budget_guard_enabled:
            max_attempts = min(max_attempts, 2)

        last_error: ExtractionError | None = None
        completion: GeminiCompletion | None = None
        for attempt_number in range(1, max_attempts + 1):
            try:
                async with self._semaphore:
                    completion = await asyncio.wait_for(
                        self._require_completer().complete(
                            model=self._settings.gemini_model_id,
                            messages=self._messages(rendered),
                            timeout_seconds=self._settings.gemini_request_timeout_seconds,
                        ),
                        timeout=self._settings.gemini_request_timeout_seconds,
                    )
                payload = parse_gemini_payload(completion.content)
                self._write_raw_output(pdf_path, pages, completion, parsed=True)
                pages_out = self._pages_from_payload(
                    pdf_path=pdf_path,
                    rendered=rendered,
                    payload_pages=payload.pages,
                )
                duration_ms = int((time.perf_counter() - started) * 1000)
                cost = estimate_cost_usd(
                    completion.prompt_tokens or 0,
                    completion.completion_tokens or 0,
                    input_usd_per_million=self._settings.gemini_input_usd_per_million,
                    output_usd_per_million=self._settings.gemini_output_usd_per_million,
                )
                attempt = ExtractionAttempt(
                    attempt=attempt_number,
                    extractor=self.name,
                    status="completed",
                    duration_ms=duration_ms,
                    element_count=sum(len(page.elements) for page in pages_out),
                )
                for page in pages_out:
                    page.attempts = [attempt.model_copy(deep=True)]
                return CanonicalExtractionResult(
                    pages=pages_out,
                    attempts=[attempt],
                    duration_ms=duration_ms,
                    metadata={
                        "page_assets": page_assets,
                        "usage": {
                            "prompt_tokens": completion.prompt_tokens,
                            "completion_tokens": completion.completion_tokens,
                            "total_tokens": completion.total_tokens,
                            "finish_reason": completion.finish_reason,
                            "model": completion.model,
                            "estimated_cost_usd": cost,
                        },
                    },
                )
            except asyncio.TimeoutError:
                last_error = ExtractionError(
                    code="GEMINI_TIMEOUT",
                    message="Gemini request timed out.",
                    details={"pages": pages, "attempt": attempt_number},
                )
            except Exception as exc:
                logger.warning("Gemini group failed on attempt %s: %s", attempt_number, exc)
                last_error = ExtractionError(
                    code="GEMINI_RESPONSE_INVALID"
                    if "JSON" in str(exc) or "json" in str(exc).lower()
                    else "GEMINI_EXTRACTION_FAILED",
                    message=str(exc),
                    details={"pages": pages, "attempt": attempt_number},
                )
                if completion is not None:
                    self._write_raw_output(pdf_path, pages, completion, parsed=False)
            if attempt_number < max_attempts:
                delay = self._settings.gemini_retry_backoff_seconds * (2 ** (attempt_number - 1))
                if delay > 0:
                    await asyncio.sleep(min(delay, 8.0))

        duration_ms = int((time.perf_counter() - started) * 1000)
        error = last_error or ExtractionError(
            code="GEMINI_EXTRACTION_FAILED",
            message="Gemini extraction failed.",
            details={"pages": pages},
        )
        failed_pages = [self._failed_page(item, error) for item in rendered]
        attempt = ExtractionAttempt(
            attempt=max_attempts,
            extractor=self.name,
            status="failed",
            duration_ms=duration_ms,
            errors=[error],
        )
        for page in failed_pages:
            page.attempts = [attempt.model_copy(deep=True)]
        return CanonicalExtractionResult(
            pages=failed_pages,
            attempts=[attempt],
            errors=[error],
            duration_ms=duration_ms,
            metadata={"page_assets": page_assets, "usage": {}},
        )

    def _messages(self, rendered: list[RenderedPage]) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": user_prompt([item.page for item in rendered])}
        ]
        for item in rendered:
            encoded = base64.b64encode(item.png_bytes).decode("ascii")
            content.append({"type": "text", "text": f"Original page {item.page}:"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{item.mime_type};base64,{encoded}"},
                }
            )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

    def _pages_from_payload(
        self,
        *,
        pdf_path: Path,
        rendered: list[RenderedPage],
        payload_pages,
    ) -> list[CanonicalPage]:
        document_id = pdf_path.parent.name
        by_page = {item.page: item for item in payload_pages}
        pages: list[CanonicalPage] = []
        for index, rendered_page in enumerate(rendered):
            payload_page = by_page.get(rendered_page.page)
            if payload_page is None and len(payload_pages) == len(rendered):
                payload_page = payload_pages[index]
            elements = []
            if payload_page is not None:
                elements = [
                    self._to_canonical_element(
                        document_id=document_id,
                        rendered=rendered_page,
                        element=element,
                        fallback_order=order,
                    )
                    for order, element in enumerate(payload_page.elements, start=1)
                ]
            pages.append(
                CanonicalPage(
                    page=rendered_page.page,
                    width=rendered_page.width,
                    height=rendered_page.height,
                    rotation=rendered_page.rotation,
                    primary_route=self.name,
                    routing_confidence=0.8,
                    overall_confidence=_page_confidence(elements),
                    routing_reasons=["Managed visual extraction via Euron Gemini"],
                    extraction_routes=[self.name],
                    elements=elements,
                    warnings=[]
                    if payload_page is not None
                    else ["Gemini response did not include this original page."],
                    errors=[]
                    if payload_page is not None
                    else [
                        ExtractionError(
                            code="GEMINI_PAGE_MISSING",
                            message="Gemini did not return this original page.",
                            page=rendered_page.page,
                        )
                    ],
                )
            )
        return pages

    def _to_canonical_element(
        self,
        *,
        document_id: str,
        rendered: RenderedPage,
        element: GeminiElement,
        fallback_order: int,
    ) -> CanonicalElement:
        reading_order = element.reading_order or fallback_order
        bbox = None
        if element.bbox is not None:
            bbox = bbox_to_pdf_points(element.bbox, rendered.width, rendered.height)
        return CanonicalElement(
            element_id=f"{document_id}:p{rendered.page}:e{reading_order}",
            type=ElementType(element.type),
            page=rendered.page,
            reading_order=reading_order,
            text=element.text,
            markdown=element.markdown,
            html=element.html,
            bbox=bbox,
            confidence=element.confidence,
            extractor=ExtractorProvenance(
                name=self.name,
                adapter_version=ADAPTER_VERSION,
                model=self._settings.gemini_model_id,
                prompt_version=self._settings.gemini_extraction_prompt_version or PROMPT_VERSION,
            ),
            provenance=ElementProvenance(source_page=rendered.page),
            metadata={"uncertain": element.uncertain, "provider": "euron"},
        )

    def _write_raw_output(
        self,
        pdf_path: Path,
        pages: list[int],
        completion: GeminiCompletion,
        *,
        parsed: bool,
    ) -> None:
        raw_dir = pdf_path.parent / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        suffix = "-".join(str(page) for page in pages)
        raw_path = raw_dir / f"gemini-pages-{suffix}.json"
        payload: dict[str, Any] = {
            "provider": "euron",
            "model": completion.model,
            "parsed": parsed,
            "finish_reason": completion.finish_reason,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
            "total_tokens": completion.total_tokens,
            "original_pages": pages,
            "content": completion.content,
        }
        try:
            raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("Unable to persist raw Gemini JSON for pages %s", pages)

    def _failed_page(self, rendered: RenderedPage, error: ExtractionError) -> CanonicalPage:
        page_error = error.model_copy(update={"page": rendered.page})
        return CanonicalPage(
            page=rendered.page,
            width=rendered.width,
            height=rendered.height,
            rotation=rendered.rotation,
            primary_route=self.name,
            routing_confidence=0.0,
            overall_confidence=0.0,
            routing_reasons=["Gemini extraction failed"],
            extraction_routes=[self.name],
            errors=[page_error],
        )


def _page_confidence(elements: list[CanonicalElement]) -> float:
    scores = [element.confidence for element in elements if element.confidence is not None]
    if not scores:
        return 0.0 if not elements else 0.6
    return sum(scores) / len(scores)
