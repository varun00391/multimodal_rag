from __future__ import annotations

from dataclasses import dataclass

from app.adapters.docling_profiles import (
    PROFILE_DIGITAL_LAYOUT,
    PROFILE_FORMULA_CODE,
    PROFILE_PRIVATE_OCR,
    PROFILE_TASK_KIND,
    parse_extractor_ref,
)
from app.models.canonical import CanonicalPage, ElementType
from app.models.jobs import ExtractionPolicy
from app.models.validation import ValidationResult
from app.routing.privacy import managed_apis_allowed, privacy_mode

FALLBACKS: dict[str, str] = {
    "NATIVE_TEXT_CORRUPT": "gemini",
    "NATIVE_TEXT_MISSING": "gemini",
    "READING_ORDER_INVALID": "docling:digital-layout",
    "TABLE_STRUCTURE_INVALID": "gemini",
    "TABLE_EMPTY": "gemini",
    "FORMULA_MISSING": "docling:formula-code",
    "VISUAL_MEANING_MISSING": "groq-vision",
    "PYMUPDF_EXTRACTION_FAILED": "docling:digital-layout",
    "DOCLING_EXTRACTION_FAILED": "gemini",
    "GEMINI_TIMEOUT": "gemini",
    "GEMINI_EXTRACTION_FAILED": "gemini",
    "GEMINI_RESPONSE_INVALID": "gemini",
    "EXTRACTION_GROUP_TIMEOUT": "gemini",
}

TRANSIENT_CODES = {
    "GEMINI_TIMEOUT",
    "GEMINI_EXTRACTION_FAILED",
    "GEMINI_RESPONSE_INVALID",
    "EXTRACTION_GROUP_TIMEOUT",
    "DOCLING_EXTRACTION_FAILED",
    "GROQ_TIMEOUT",
    "GROQ_EXTRACTION_FAILED",
    "GROQ_RESPONSE_INVALID",
}

SKIP_CODES = {
    "SCANNED_PAGE_NOT_EXTRACTED",
    "GEMINI_NOT_CONFIGURED",
    "MANAGED_APIS_PROHIBITED",
    "PAGE_NOT_ROUTED",
}

CODE_PRIORITY = (
    "NATIVE_TEXT_CORRUPT",
    "NATIVE_TEXT_MISSING",
    "TABLE_STRUCTURE_INVALID",
    "TABLE_EMPTY",
    "READING_ORDER_INVALID",
    "FORMULA_MISSING",
    "VISUAL_MEANING_MISSING",
    "PYMUPDF_EXTRACTION_FAILED",
    "DOCLING_EXTRACTION_FAILED",
    "GEMINI_TIMEOUT",
    "GEMINI_EXTRACTION_FAILED",
    "GEMINI_RESPONSE_INVALID",
    "EXTRACTION_GROUP_TIMEOUT",
)


@dataclass(frozen=True)
class FallbackChoice:
    page: int
    reason_code: str
    extractor: str
    profile: str | None
    kind: str
    privacy_mode: str | None
    retry_same: bool = False
    regions: tuple[tuple[float, float, float, float], ...] = ()


def failure_codes(page: CanonicalPage, validation: ValidationResult | None) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    if validation is not None:
        for failure in validation.failures:
            if failure.code not in seen:
                codes.append(failure.code)
                seen.add(failure.code)
    for error in page.errors:
        if error.code not in seen:
            codes.append(error.code)
            seen.add(error.code)
    return codes


def select_fallback(
    page: CanonicalPage,
    validation: ValidationResult | None,
    policy: ExtractionPolicy,
    *,
    gemini_ready: bool,
    max_attempts: int,
    groq_ready: bool = False,
) -> FallbackChoice | None:
    if policy.force_extractor:
        return None
    if len(page.attempts) >= max(1, max_attempts):
        return None
    if any(error.code in SKIP_CODES for error in page.errors) and not _has_trigger_code(page, validation):
        return None

    codes = failure_codes(page, validation)
    trigger_codes = [code for code in CODE_PRIORITY if code in codes]
    if validation is not None and validation.passed and not trigger_codes:
        return None
    if not trigger_codes:
        trigger_codes = [code for code in codes if code in FALLBACKS]

    for code in trigger_codes:
        target = FALLBACKS.get(code)
        if not target:
            continue
        if target.startswith("groq"):
            choice = _groq_choice(page, code, policy, groq_ready=groq_ready)
            if choice is not None:
                return choice
            continue
        choice = _resolve_target(
            page,
            code,
            target,
            policy,
            gemini_ready=gemini_ready,
        )
        if choice is not None:
            return choice
    return None


def _groq_choice(
    page: CanonicalPage,
    reason_code: str,
    policy: ExtractionPolicy,
    *,
    groq_ready: bool,
) -> FallbackChoice | None:
    if not groq_ready or not managed_apis_allowed(policy) or not policy.visual_understanding:
        return None
    if _already_tried(page, "groq-vision", None):
        return None
    regions = tuple(_missing_visual_regions(page))
    if not regions:
        return None
    return FallbackChoice(
        page=page.page,
        reason_code=reason_code,
        extractor="groq-vision",
        profile=None,
        kind="visual_understanding",
        privacy_mode="managed",
        regions=regions,
    )


def _missing_visual_regions(page: CanonicalPage) -> list[tuple[float, float, float, float]]:
    regions: list[tuple[float, float, float, float]] = []
    for element in page.elements:
        if element.type not in {ElementType.CHART, ElementType.DIAGRAM, ElementType.PICTURE}:
            continue
        if (element.text or "").strip():
            continue
        if element.bbox is None:
            continue
        regions.append((element.bbox.left, element.bbox.top, element.bbox.right, element.bbox.bottom))
    return regions


def _has_trigger_code(page: CanonicalPage, validation: ValidationResult | None) -> bool:
    return any(code in FALLBACKS for code in failure_codes(page, validation))


def _resolve_target(
    page: CanonicalPage,
    reason_code: str,
    target: str,
    policy: ExtractionPolicy,
    *,
    gemini_ready: bool,
) -> FallbackChoice | None:
    chain = _candidate_chain(target, policy, gemini_ready=gemini_ready)
    for extractor, profile in chain:
        if extractor == "gemini" and not gemini_ready:
            continue
        retry_same = _can_retry_same(page, extractor, profile, reason_code)
        if _already_tried(page, extractor, profile) and not retry_same:
            continue
        kind = _kind_for(extractor, profile)
        return FallbackChoice(
            page=page.page,
            reason_code=reason_code,
            extractor=extractor,
            profile=profile,
            kind=kind,
            privacy_mode="managed" if extractor == "gemini" else privacy_mode(policy),
            retry_same=retry_same,
        )
    return None


def _candidate_chain(
    target: str,
    policy: ExtractionPolicy,
    *,
    gemini_ready: bool,
) -> list[tuple[str, str | None]]:
    extractor, profile = parse_extractor_ref(target)
    if extractor is None:
        return []
    if extractor == "docling" and profile is None:
        profile = PROFILE_DIGITAL_LAYOUT

    chain: list[tuple[str, str | None]] = []
    if extractor == "gemini":
        if managed_apis_allowed(policy) and gemini_ready:
            chain.append(("gemini", None))
        chain.append(("docling", PROFILE_PRIVATE_OCR))
    elif extractor == "docling":
        chain.append(("docling", profile))
        if managed_apis_allowed(policy) and gemini_ready:
            chain.append(("gemini", None))
    else:
        chain.append((extractor, profile))
    return chain


def _already_tried(page: CanonicalPage, extractor: str, profile: str | None) -> bool:
    return any(
        attempt.extractor == extractor and (attempt.profile or None) == (profile or None)
        for attempt in page.attempts
    )


def _can_retry_same(
    page: CanonicalPage,
    extractor: str,
    profile: str | None,
    reason_code: str,
) -> bool:
    if reason_code not in TRANSIENT_CODES:
        return False
    count = sum(
        1
        for attempt in page.attempts
        if attempt.extractor == extractor and (attempt.profile or None) == (profile or None)
    )
    return 0 < count < 2


def _kind_for(extractor: str, profile: str | None) -> str:
    if extractor == "gemini":
        return "ocr"
    if extractor == "groq-vision":
        return "visual_understanding"
    if extractor == "docling":
        if profile == PROFILE_FORMULA_CODE:
            return PROFILE_TASK_KIND[PROFILE_FORMULA_CODE]
        if profile == PROFILE_PRIVATE_OCR:
            return PROFILE_TASK_KIND[PROFILE_PRIVATE_OCR]
        if profile == PROFILE_DIGITAL_LAYOUT:
            return PROFILE_TASK_KIND[PROFILE_DIGITAL_LAYOUT]
        return PROFILE_TASK_KIND.get(profile or "", "layout")
    return "native_text"
