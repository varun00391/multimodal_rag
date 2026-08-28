from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.models.canonical import CanonicalPage, ElementType, ExtractionError
from app.models.inspection import DocumentInspection, PageInspection
from app.models.validation import ValidationFailure, ValidationResult
from app.validation.codes import HARD_FAILURE_CODES
from app.validation.layout import validate_layout
from app.validation.tables import validate_tables
from app.validation.text import validate_text
from app.validation.visuals import validate_visuals


class PageValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate_pages(
        self,
        pages: list[CanonicalPage],
        inspection: DocumentInspection,
        *,
        workspace: Path | None = None,
    ) -> list[ValidationResult]:
        by_page = {page.page: page for page in inspection.pages}
        results: list[ValidationResult] = []
        for page in pages:
            results.append(
                self.apply(
                    page,
                    by_page.get(page.page),
                    workspace=workspace,
                )
            )
        return results

    def apply(
        self,
        page: CanonicalPage,
        inspection: PageInspection | None,
        *,
        workspace: Path | None = None,
    ) -> ValidationResult:
        failures = [
            *validate_text(page, inspection),
            *validate_layout(page),
            *validate_tables(page, inspection),
            *validate_visuals(page, inspection, workspace=workspace),
            *_formula_failures(page, inspection),
        ]
        hard = [item for item in failures if item.code in HARD_FAILURE_CODES]
        soft_count = len(failures) - len(hard)
        confidence = max(0.0, round(1.0 - (0.20 * len(hard)) - (0.05 * soft_count), 4))
        passed = not hard and confidence >= self._settings.extraction_min_validation_confidence

        page.validation_confidence = confidence
        parser_confidence = _parser_confidence(page)
        routing_confidence = page.routing_confidence if page.routing_confidence is not None else 1.0
        page.overall_confidence = min(routing_confidence, parser_confidence, confidence)

        existing_codes = {error.code for error in page.errors}
        for failure in hard:
            if failure.code in existing_codes:
                continue
            page.errors.append(
                ExtractionError(
                    code=failure.code,
                    message=failure.message,
                    page=page.page,
                    details=dict(failure.details),
                )
            )
            existing_codes.add(failure.code)
        for failure in failures:
            if failure.code in HARD_FAILURE_CODES:
                continue
            warning = f"{failure.code}: {failure.message}"
            if warning not in page.warnings:
                page.warnings.append(warning)

        return ValidationResult(
            page=page.page,
            confidence=confidence,
            passed=passed,
            failures=failures,
        )


def _parser_confidence(page: CanonicalPage) -> float:
    scores = [element.confidence for element in page.elements if element.confidence is not None]
    if scores:
        return sum(scores) / len(scores)
    if page.errors and not page.elements:
        return 0.0
    return 1.0


def _formula_failures(
    page: CanonicalPage,
    inspection: PageInspection | None,
) -> list[ValidationFailure]:
    if inspection is None or inspection.layout.formula_like_regions <= 0:
        return []
    has_structure = any(
        element.type in {ElementType.FORMULA, ElementType.CODE} for element in page.elements
    )
    if has_structure:
        return []
    return [
        ValidationFailure(
            code="FORMULA_MISSING",
            message="Inspection found formula-like regions but no formula or code element was extracted.",
            details={"formula_like_regions": inspection.layout.formula_like_regions},
        )
    ]
