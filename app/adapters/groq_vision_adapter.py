from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.adapters.groq_client import GroqCompleter, GroqCompletion, GroqVisionClient
from app.adapters.groq_crops import VisualCrop, crop_region
from app.adapters.groq_prompt import PROMPT_VERSION, SYSTEM_PROMPT, user_prompt
from app.adapters.groq_schema import parse_groq_payload
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


class GroqVisionAdapter:
    name = "groq-vision"

    def __init__(
        self,
        settings: Settings,
        *,
        completer: GroqCompleter | None = None,
    ) -> None:
        self._settings = settings
        self._completer = completer
        self._semaphore = asyncio.Semaphore(max(1, settings.groq_max_concurrency))

    @property
    def is_configured(self) -> bool:
        return self._completer is not None or bool(self._settings.groq_api_key)

    def _require_completer(self) -> GroqCompleter:
        if self._completer is not None:
            return self._completer
        if not self._settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required to call Groq vision.")
        self._completer = GroqVisionClient(self._settings)
        return self._completer

    async def extract(
        self,
        pdf_path: Path,
        pages: list[int],
        tasks: list[ExtractionTask],
        context_pages: list[int] | None = None,
    ) -> CanonicalExtractionResult:
        started = time.perf_counter()
        requested = list(pages)
        region_tasks = [task for task in tasks if task.page in set(requested)]
        if not region_tasks:
            region_tasks = [
                ExtractionTask(page=page_number, kind="visual_understanding", extractor=self.name)
                for page_number in requested
            ]

        crops: list[tuple[ExtractionTask, VisualCrop | None, ExtractionError | None]] = []
        for index, task in enumerate(region_tasks, start=1):
            region = task.region
            if not region or len(region) != 4:
                crops.append(
                    (
                        task,
                        None,
                        ExtractionError(
                            code="VISUAL_REGION_MISSING",
                            message="Groq vision requires a figure bounding box.",
                            page=task.page,
                        ),
                    )
                )
                continue
            try:
                crop = await asyncio.to_thread(
                    crop_region,
                    pdf_path,
                    task.page,
                    region,
                    index=index,
                    max_pixels=min(4_000_000, self._settings.extraction_max_rendered_pixels),
                )
                crops.append((task, crop, None))
            except Exception as exc:
                logger.warning("Failed to crop visual region on page %s: %s", task.page, exc)
                crops.append(
                    (
                        task,
                        None,
                        ExtractionError(
                            code="VISUAL_CROP_MISSING",
                            message=str(exc),
                            page=task.page,
                        ),
                    )
                )

        results = await asyncio.gather(
            *[self._interpret(pdf_path, task, crop, error) for task, crop, error in crops]
        )

        pages_out: dict[int, CanonicalPage] = {}
        attempts: list[ExtractionAttempt] = []
        warnings: list[str] = []
        errors: list[ExtractionError] = []
        prompt_tokens = 0
        completion_tokens = 0
        finish_reasons: list[str] = []
        for page_number, element, attempt, error, usage in results:
            page = pages_out.setdefault(
                page_number,
                CanonicalPage(
                    page=page_number,
                    width=0,
                    height=0,
                    primary_route=self.name,
                    extraction_routes=[self.name],
                    routing_reasons=["Groq vision region interpretation"],
                ),
            )
            if element is not None:
                page.elements.append(element)
                if element.bbox:
                    page.width = max(page.width, element.bbox.right + 24)
                    page.height = max(page.height, element.bbox.bottom + 24)
            if attempt is not None:
                page.attempts.append(attempt)
                attempts.append(attempt)
            if error is not None:
                page.errors.append(error)
                errors.append(error)
            prompt_tokens += int((usage or {}).get("prompt_tokens") or 0)
            completion_tokens += int((usage or {}).get("completion_tokens") or 0)
            if (usage or {}).get("finish_reason"):
                finish_reasons.append(str(usage["finish_reason"]))

        duration_ms = int((time.perf_counter() - started) * 1000)
        ordered = [pages_out[page_number] for page_number in requested if page_number in pages_out]
        for extra_page in pages_out:
            if extra_page not in requested:
                ordered.append(pages_out[extra_page])
        return CanonicalExtractionResult(
            pages=ordered,
            attempts=attempts,
            warnings=warnings,
            errors=errors,
            duration_ms=duration_ms,
            metadata={
                "provider": "groq",
                "model": self._settings.groq_visual_model,
                "prompt_version": self._settings.groq_visual_prompt_version or PROMPT_VERSION,
                "adapter_version": ADAPTER_VERSION,
                "usage": {
                    "prompt_tokens": prompt_tokens or None,
                    "completion_tokens": completion_tokens or None,
                    "total_tokens": (prompt_tokens + completion_tokens) or None,
                    "estimated_cost_usd": 0.0,
                    "finish_reasons": finish_reasons,
                },
            },
        )

    async def _interpret(
        self,
        pdf_path: Path,
        task: ExtractionTask,
        crop: VisualCrop | None,
        crop_error: ExtractionError | None,
    ) -> tuple[int, CanonicalElement | None, ExtractionAttempt | None, ExtractionError | None, dict[str, Any]]:
        if crop is None:
            attempt = ExtractionAttempt(
                attempt=1,
                extractor=self.name,
                status="failed",
                errors=[crop_error] if crop_error else [],
            )
            return task.page, None, attempt, crop_error, {}

        started = time.perf_counter()
        try:
            async with self._semaphore:
                completion = await asyncio.wait_for(
                    self._require_completer().complete(
                        model=self._settings.groq_visual_model,
                        messages=self._messages(crop),
                        timeout_seconds=self._settings.groq_request_timeout_seconds,
                    ),
                    timeout=self._settings.groq_request_timeout_seconds,
                )
            payload = parse_groq_payload(completion.content)
            self._write_raw_output(pdf_path, crop, completion, parsed=True)
            element = self._element_from_payload(crop, payload)
            duration_ms = int((time.perf_counter() - started) * 1000)
            attempt = ExtractionAttempt(
                attempt=1,
                extractor=self.name,
                status="completed",
                duration_ms=duration_ms,
                element_count=1,
            )
            usage = {
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "finish_reason": completion.finish_reason,
            }
            return crop.page, element, attempt, None, usage
        except asyncio.TimeoutError:
            error = ExtractionError(
                code="GROQ_TIMEOUT",
                message="Groq vision request timed out.",
                page=task.page,
            )
        except Exception as exc:
            logger.warning("Groq vision failed for page %s: %s", task.page, exc)
            error = ExtractionError(
                code="GROQ_RESPONSE_INVALID"
                if "JSON" in str(exc) or "json" in str(exc).lower()
                else "GROQ_EXTRACTION_FAILED",
                message=str(exc),
                page=task.page,
            )
        attempt = ExtractionAttempt(
            attempt=1,
            extractor=self.name,
            status="failed",
            errors=[error],
        )
        return task.page, None, attempt, error, {}

    def _messages(self, crop: VisualCrop) -> list[dict[str, Any]]:
        encoded = base64.b64encode(crop.png_bytes).decode("ascii")
        prompt = user_prompt(
            page=crop.page,
            bbox=[crop.bbox.left, crop.bbox.top, crop.bbox.right, crop.bbox.bottom],
            nearby_text=crop.nearby_text,
            caption=crop.caption,
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded}"},
                    },
                ],
            },
        ]

    def _element_from_payload(self, crop: VisualCrop, payload) -> CanonicalElement:
        description = (payload.description or "").strip() or None
        title = (payload.title or "").strip() or None
        caption = (payload.caption or crop.caption or "").strip() or None
        text_parts = [part for part in (title, description, caption) if part]
        visual_type = ElementType(payload.type)
        return CanonicalElement(
            element_id=f"groq:p{crop.page}:r{int(crop.bbox.top)}",
            type=visual_type,
            page=crop.page,
            reading_order=1,
            text=description,
            markdown=description,
            bbox=crop.bbox,
            asset=crop.asset,
            confidence=0.4 if payload.uncertain else 0.8,
            extractor=ExtractorProvenance(
                name=self.name,
                adapter_version=ADAPTER_VERSION,
                model=self._settings.groq_visual_model,
                prompt_version=self._settings.groq_visual_prompt_version or PROMPT_VERSION,
            ),
            provenance=ElementProvenance(source_page=crop.page),
            metadata={
                "title": title,
                "caption": caption,
                "uncertain": payload.uncertain,
                "nearby_text": crop.nearby_text,
                "provider": "groq",
                "combined_text": " ".join(text_parts),
            },
        )

    def _write_raw_output(
        self,
        pdf_path: Path,
        crop: VisualCrop,
        completion: GroqCompletion,
        *,
        parsed: bool,
    ) -> None:
        raw_dir = pdf_path.parent / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": "groq",
            "model": completion.model,
            "parsed": parsed,
            "finish_reason": completion.finish_reason,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
            "page": crop.page,
            "bbox": [crop.bbox.left, crop.bbox.top, crop.bbox.right, crop.bbox.bottom],
            "content": completion.content,
        }
        (raw_dir / f"groq-page-{crop.page}-r{int(crop.bbox.top)}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
