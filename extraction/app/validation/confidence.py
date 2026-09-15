from __future__ import annotations

from app.core.config import get_settings
from app.models.common import ConfidenceBand, ValidationStatus
from app.models.validation import ValidationResult


def band_for(score: float) -> ConfidenceBand:
    settings = get_settings()
    if score >= settings.confidence_high:
        return ConfidenceBand.HIGH
    if score >= settings.confidence_medium:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def score_confidence(
    *,
    source_agreement: float,
    extraction_quality: float,
    structural_consistency: float = 1.0,
    semantic_consistency: float = 1.0,
    visual_confidence: float = 1.0,
    weights: tuple[float, float, float, float, float] = (0.30, 0.25, 0.20, 0.15, 0.10),
) -> float:
    parts = [
        source_agreement,
        extraction_quality,
        structural_consistency,
        semantic_consistency,
        visual_confidence,
    ]
    total = sum(max(0.0, min(1.0, value)) * weight for value, weight in zip(parts, weights))
    return round(max(0.0, min(1.0, total)), 4)


def build_validation(
    *,
    confidence: float,
    status: ValidationStatus,
    reasons: list[str] | None = None,
    candidates: list | None = None,
    checks: dict | None = None,
) -> ValidationResult:
    settings = get_settings()
    needs_review = (
        confidence < settings.review_confidence_threshold
        or status
        in {
            ValidationStatus.CONFLICT,
            ValidationStatus.UNREADABLE,
            ValidationStatus.LOW_CONFIDENCE,
        }
    )
    if needs_review and status == ValidationStatus.VERIFIED:
        status = ValidationStatus.PENDING_REVIEW
    return ValidationResult(
        confidence=confidence,
        band=band_for(confidence),
        status=status,
        reasons=reasons or [],
        needs_review=needs_review,
        candidates=candidates or [],
        checks=checks or {},
    )
