from __future__ import annotations

from collections import defaultdict

from app.execution.executor import GroupRun
from app.models.canonical import (
    CanonicalElement,
    CanonicalPage,
    ElementType,
    ExtractionAttempt,
    ExtractionError,
)
from app.models.inspection import DocumentInspection, PageInspection
from app.models.routing import PagePlan
from app.services.document_builder import build_failed_page, build_scanned_page


def combine_pages(
    inspection: DocumentInspection,
    plans: list[PagePlan],
    runs: list[GroupRun],
) -> list[CanonicalPage]:
    plan_by_page = {plan.page: plan for plan in plans}
    fragments_by_page: dict[int, list[CanonicalPage]] = defaultdict(list)
    failed_by_page: dict[int, list[tuple[GroupRun, ExtractionError]]] = defaultdict(list)

    for run in runs:
        target_pages = set(run.group.pages)
        if run.error is not None:
            for page_number in run.group.pages:
                failed_by_page[page_number].append((run, run.error))
            continue
        if run.result is None:
            continue
        for page in run.result.pages:
            if page.page in target_pages:
                fragments_by_page[page.page].append(page)

    combined: list[CanonicalPage] = []
    for page_inspection in inspection.pages:
        plan = plan_by_page.get(page_inspection.page) or PagePlan(page=page_inspection.page)
        fragments = fragments_by_page.get(page_inspection.page, [])
        failures = failed_by_page.get(page_inspection.page, [])
        if not plan.tasks:
            combined.append(_unextracted_page(page_inspection, plan))
        elif fragments:
            combined.append(_merge_fragments(page_inspection, plan, fragments, failures))
        else:
            combined.append(_failed_page(page_inspection, plan, failures))
    return combined


def _unextracted_page(page_inspection: PageInspection, plan: PagePlan) -> CanonicalPage:
    reasons = [reason.lower() for reason in plan.reasons]
    joined = " ".join(reasons)
    if "prohibited" in joined:
        extractor = "groq-vision" if "groq" in joined else "gemini"
        return build_failed_page(
            page_inspection,
            extractor=extractor,
            profile=None,
            error=ExtractionError(
                code="MANAGED_APIS_PROHIBITED",
                message=(
                    "Groq vision was requested but managed APIs are not allowed."
                    if extractor == "groq-vision"
                    else "Gemini was requested but managed APIs are not allowed."
                ),
                page=page_inspection.page,
            ),
        )
    if "scanned" in joined:
        return build_scanned_page(page_inspection)
    if "not configured" in joined or "euri_api_key" in joined:
        if "groq" in joined:
            return build_failed_page(
                page_inspection,
                extractor="groq-vision",
                profile=None,
                error=ExtractionError(
                    code="GROQ_NOT_CONFIGURED",
                    message="Groq vision requires GROQ_API_KEY.",
                    page=page_inspection.page,
                ),
            )
        return build_failed_page(
            page_inspection,
            extractor="gemini",
            profile=None,
            error=ExtractionError(
                code="GEMINI_NOT_CONFIGURED",
                message="Gemini through Euron requires EURI_API_KEY.",
                page=page_inspection.page,
            ),
        )
    return build_failed_page(
        page_inspection,
        extractor=plan.primary_route or "none",
        profile=None,
        error=ExtractionError(
            code="PAGE_NOT_ROUTED",
            message="No extractor was selected for this page.",
            page=page_inspection.page,
        ),
    )


def _failed_page(
    page_inspection: PageInspection,
    plan: PagePlan,
    failures: list[tuple[GroupRun, ExtractionError]],
) -> CanonicalPage:
    if failures:
        run, error = failures[0]
        return build_failed_page(
            page_inspection,
            extractor=run.group.extractor,
            profile=run.group.profile,
            error=error,
        )
    extractor = plan.primary_route or (plan.tasks[0].extractor if plan.tasks else "none")
    profile = plan.tasks[0].profile if plan.tasks else None
    return build_failed_page(
        page_inspection,
        extractor=extractor,
        profile=profile,
        error=ExtractionError(
            code="EXTRACTION_GROUP_FAILED",
            message="No extraction result was produced for this page.",
            page=page_inspection.page,
        ),
    )


def _merge_fragments(
    page_inspection: PageInspection,
    plan: PagePlan,
    fragments: list[CanonicalPage],
    failures: list[tuple[GroupRun, ExtractionError]],
) -> CanonicalPage:
    elements: list[CanonicalElement] = []
    attempts: list[ExtractionAttempt] = []
    warnings: list[str] = []
    errors: list[ExtractionError] = []
    routes: list[str] = []

    for fragment in fragments:
        elements.extend(fragment.elements)
        attempts.extend(fragment.attempts)
        warnings.extend(fragment.warnings)
        errors.extend(fragment.errors)
        for route in fragment.extraction_routes:
            if route and route not in routes:
                routes.append(route)

    for run, error in failures:
        page_error = error.model_copy(update={"page": page_inspection.page})
        errors.append(page_error)
        attempts.append(
            ExtractionAttempt(
                attempt=len(attempts) + 1,
                extractor=run.group.extractor,
                profile=run.group.profile,
                status="failed",
                errors=[page_error],
            )
        )
        warnings.append(
            f"{run.group.extractor} group '{run.group.group_id}' failed and was not merged."
        )

    elements = _drop_pymupdf_tables_if_docling_present(elements)
    elements = _resequence_elements(page_inspection.page, elements)

    for index, attempt in enumerate(attempts, start=1):
        attempt.attempt = index

    planned_routes = [task.extractor for task in plan.tasks if task.extractor]
    extraction_routes = list(dict.fromkeys(planned_routes + routes))
    confidences = [fragment.overall_confidence for fragment in fragments if fragment.overall_confidence]
    overall = max(confidences) if confidences else (0.9 if elements else 0.0)

    return CanonicalPage(
        page=page_inspection.page,
        width=page_inspection.width,
        height=page_inspection.height,
        rotation=page_inspection.rotation,
        primary_route=plan.primary_route,
        routing_confidence=0.9 if plan.tasks else 0.0,
        overall_confidence=overall,
        routing_reasons=list(plan.reasons),
        extraction_routes=extraction_routes,
        elements=elements,
        attempts=attempts,
        warnings=list(dict.fromkeys(warnings)),
        errors=errors,
    )


def _drop_pymupdf_tables_if_docling_present(elements: list[CanonicalElement]) -> list[CanonicalElement]:
    has_docling_table = any(
        element.type == ElementType.TABLE and _extractor_name(element) == "docling"
        for element in elements
    )
    if not has_docling_table:
        return elements
    return [
        element
        for element in elements
        if not (element.type == ElementType.TABLE and _extractor_name(element) == "pymupdf")
    ]


def _extractor_name(element: CanonicalElement) -> str | None:
    if element.extractor is None:
        return None
    return element.extractor.name


def _resequence_elements(page_number: int, elements: list[CanonicalElement]) -> list[CanonicalElement]:
    ordered = sorted(elements, key=_reading_key)
    resequenced: list[CanonicalElement] = []
    for index, element in enumerate(ordered, start=1):
        updated = element.model_copy(deep=True)
        updated.reading_order = index
        updated.element_id = f"p{page_number}:e{index}"
        resequenced.append(updated)
    return resequenced


def _reading_key(element: CanonicalElement) -> tuple[float, float, int]:
    if element.bbox is not None:
        return (round(element.bbox.top, 1), element.bbox.left, element.reading_order)
    return (float(element.reading_order), 0.0, element.reading_order)
