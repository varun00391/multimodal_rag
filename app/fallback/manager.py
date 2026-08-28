from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.adapters.gemini_pages import persist_rendered_pages, render_pages
from app.config import Settings
from app.execution.executor import ExtractionExecutor, GroupRun
from app.fallback.policy import FallbackChoice, select_fallback
from app.merge.merger import absorb_fallback, finalize_pages
from app.models.canonical import CanonicalPage, ExtractionAttempt, ExtractionError
from app.models.inspection import DocumentInspection
from app.models.jobs import ExtractionPolicy
from app.models.routing import ExtractionGroup, ExtractionTask
from app.models.validation import ValidationResult
from app.validation.validator import PageValidator

logger = logging.getLogger(__name__)


@dataclass
class FallbackRecord:
    page: int
    reason_code: str
    from_extractor: str | None
    to_extractor: str
    to_profile: str | None
    status: str
    message: str


@dataclass
class FallbackResolution:
    pages: list[CanonicalPage]
    records: list[FallbackRecord] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    gemini_finish_reasons: list[str] = field(default_factory=list)
    validations: list[ValidationResult] = field(default_factory=list)


class FallbackManager:
    def __init__(
        self,
        settings: Settings,
        executor: ExtractionExecutor,
        validator: PageValidator,
    ) -> None:
        self._settings = settings
        self._executor = executor
        self._validator = validator

    async def resolve(
        self,
        pdf_path: Path,
        pages: list[CanonicalPage],
        validations: list[ValidationResult],
        inspection: DocumentInspection,
        policy: ExtractionPolicy,
        *,
        document_id: str,
        gemini_ready: bool,
        groq_ready: bool = False,
        workspace: Path | None = None,
    ) -> FallbackResolution:
        records: list[FallbackRecord] = []
        prompt_tokens = 0
        completion_tokens = 0
        estimated_cost_usd = 0.0
        finish_reasons: list[str] = []
        pages_by_number = {page.page: page for page in pages}
        validation_by_page = {item.page: item for item in validations}
        max_attempts = max(1, self._settings.extraction_max_attempts_per_page)

        for _round in range(max_attempts):
            choices: list[FallbackChoice] = []
            for page_inspection in inspection.pages:
                page = pages_by_number.get(page_inspection.page)
                if page is None:
                    continue
                choice = select_fallback(
                    page,
                    validation_by_page.get(page.page),
                    policy,
                    gemini_ready=gemini_ready,
                    groq_ready=groq_ready,
                    max_attempts=max_attempts,
                )
                if choice is not None:
                    choices.append(choice)
            if not choices:
                break

            if any(choice.retry_same for choice in choices):
                delay = self._settings.gemini_retry_backoff_seconds
                if delay > 0:
                    await asyncio.sleep(min(delay, 8.0))

            runs = await self._executor.run(
                pdf_path,
                [_group_for_choice(choice, document_id) for choice in choices],
            )
            choice_by_page = {choice.page: choice for choice in choices}
            for run in runs:
                usage = _usage(run)
                prompt_tokens += usage[0]
                completion_tokens += usage[1]
                estimated_cost_usd += usage[2]
                finish_reasons.extend(usage[3])
                for page_number in run.group.pages:
                    original = pages_by_number[page_number]
                    choice = choice_by_page[page_number]
                    records.append(_apply_run(original, run, choice))

            finalized = finalize_pages(list(pages_by_number.values()), inspection)
            pages_by_number = {page.page: page for page in finalized}
            fresh = self._validator.validate_pages(
                [pages_by_number[item.page] for item in inspection.pages],
                inspection,
                workspace=workspace,
            )
            validation_by_page = {item.page: item for item in fresh}

        remaining_failed = [
            page for page in pages_by_number.values() if page.errors and not page.elements
        ]
        if remaining_failed:
            await _preserve_page_images(
                pdf_path,
                remaining_failed,
                max_pixels=self._settings.extraction_max_rendered_pixels,
            )

        ordered = [pages_by_number[item.page] for item in inspection.pages]
        return FallbackResolution(
            pages=ordered,
            records=records,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=estimated_cost_usd,
            gemini_finish_reasons=finish_reasons,
            validations=[
                validation_by_page[page.page]
                for page in ordered
                if page.page in validation_by_page
            ],
        )


def _group_for_choice(choice: FallbackChoice, document_id: str) -> ExtractionGroup:
    regions = list(choice.regions) or [None]
    tasks = [
        ExtractionTask(
            document_id=document_id,
            page=choice.page,
            kind=choice.kind,
            extractor=choice.extractor,
            profile=choice.profile,
            required=True,
            options_hash="retry" if choice.retry_same else "fallback",
            privacy_mode=choice.privacy_mode,
            region=list(region) if region is not None else None,
        )
        for region in regions
    ]
    return ExtractionGroup(
        group_id=f"fallback-{choice.extractor}-{choice.page:04d}",
        document_id=document_id,
        extractor=choice.extractor,
        profile=choice.profile,
        kind=choice.kind,
        pages=[choice.page],
        options_hash=tasks[0].options_hash,
        privacy_mode=choice.privacy_mode,
        tasks=tasks,
        metadata={"fallback": True, "reason_code": choice.reason_code},
    )


def _apply_run(original: CanonicalPage, run: GroupRun, choice: FallbackChoice) -> FallbackRecord:
    from_extractor = original.primary_route
    if run.error is not None:
        page_error = run.error.model_copy(update={"page": original.page})
        original.errors.append(page_error)
        original.attempts.append(
            ExtractionAttempt(
                attempt=len(original.attempts) + 1,
                extractor=choice.extractor,
                profile=choice.profile,
                status="failed",
                errors=[page_error],
            )
        )
        original.warnings.append(f"Fallback {choice.extractor} failed for {choice.reason_code}.")
        return FallbackRecord(
            page=original.page,
            reason_code=choice.reason_code,
            from_extractor=from_extractor,
            to_extractor=choice.extractor,
            to_profile=choice.profile,
            status="failed",
            message=run.error.message,
        )

    fallback_page = None
    if run.result is not None:
        fallback_page = next((page for page in run.result.pages if page.page == original.page), None)
        if fallback_page is None and run.result.pages:
            fallback_page = run.result.pages[0]
            fallback_page.page = original.page
    if fallback_page is None:
        original.attempts.append(
            ExtractionAttempt(
                attempt=len(original.attempts) + 1,
                extractor=choice.extractor,
                profile=choice.profile,
                status="failed",
                errors=[
                    ExtractionError(
                        code="FALLBACK_EMPTY_RESULT",
                        message="Fallback extractor returned no page result.",
                        page=original.page,
                    )
                ],
            )
        )
        return FallbackRecord(
            page=original.page,
            reason_code=choice.reason_code,
            from_extractor=from_extractor,
            to_extractor=choice.extractor,
            to_profile=choice.profile,
            status="failed",
            message="Fallback extractor returned no page result.",
        )

    absorb_fallback(original, fallback_page, choice.reason_code)
    original.warnings.append(f"Fallback {choice.extractor} applied for {choice.reason_code}.")
    return FallbackRecord(
        page=original.page,
        reason_code=choice.reason_code,
        from_extractor=from_extractor,
        to_extractor=choice.extractor,
        to_profile=choice.profile,
        status="completed",
        message=f"Retried failed work with {choice.extractor}.",
    )


def _usage(run: GroupRun) -> tuple[int, int, float, list[str]]:
    if run.result is None:
        return 0, 0, 0.0, []
    usage = run.result.metadata.get("usage") or {}
    finish = [str(item) for item in (usage.get("finish_reasons") or []) if item]
    if usage.get("finish_reason"):
        finish.append(str(usage["finish_reason"]))
    return (
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
        float(usage.get("estimated_cost_usd") or 0.0),
        finish,
    )


async def _preserve_page_images(
    pdf_path: Path,
    pages: list[CanonicalPage],
    *,
    max_pixels: int,
) -> None:
    page_numbers = [page.page for page in pages]
    try:
        rendered = await asyncio.to_thread(
            render_pages, pdf_path, page_numbers, max_pixels=max_pixels
        )
        assets = persist_rendered_pages(pdf_path, rendered)
    except Exception:
        logger.exception("Failed to retain source page images after exhausted fallbacks")
        assets = []
    asset_by_page = {
        page.page: asset for page, asset in zip(pages, assets)
    }
    for page in pages:
        asset = asset_by_page.get(page.page)
        page.errors.append(
            ExtractionError(
                code="EXTRACTION_EXHAUSTED",
                message="All extractors failed for this page; the source page image was retained when possible.",
                page=page.page,
                details={"page_image": asset} if asset else {},
            )
        )
        if asset:
            page.warnings.append(f"Source page image retained at {asset}.")
