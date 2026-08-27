from __future__ import annotations

from pathlib import Path

from app.models.canonical import (
    CanonicalDocument,
    CanonicalPage,
    DocumentSource,
    DocumentSummary,
    ExtractionError,
)
from app.models.inspection import DocumentInspection, PageInspection


def build_scanned_page(page_inspection: PageInspection) -> CanonicalPage:
    return CanonicalPage(
        page=page_inspection.page,
        width=page_inspection.width,
        height=page_inspection.height,
        rotation=page_inspection.rotation,
        primary_route=None,
        routing_confidence=0.95,
        overall_confidence=0.0,
        routing_reasons=["Page classified as probable scan during inspection"],
        extraction_routes=[],
        warnings=[
            "Page appears to be scanned; PyMuPDF text extraction skipped in Phase 2 baseline."
        ],
        errors=[
            ExtractionError(
                code="SCANNED_PAGE_NOT_EXTRACTED",
                message="Scanned pages are identified but not yet fully extracted.",
                page=page_inspection.page,
            )
        ],
    )


def build_document(
    *,
    schema_version: str,
    document_id: str,
    source: DocumentSource,
    inspection: DocumentInspection,
    pages: list[CanonicalPage],
    duration_ms: int,
) -> CanonicalDocument:
    element_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    scanned_pages: list[int] = []
    failed_pages: list[int] = []

    for page in pages:
        if page.errors:
            failed_pages.append(page.page)
        for element in page.elements:
            element_counts[element.type.value] = element_counts.get(element.type.value, 0) + 1
        if page.primary_route:
            route_counts[page.primary_route] = route_counts.get(page.primary_route, 0) + 1

    for page_inspection in inspection.pages:
        if page_inspection.probable_scan:
            scanned_pages.append(page_inspection.page)

    has_warnings = bool(scanned_pages or failed_pages)
    status = "completed_with_warnings" if has_warnings else "completed"

    return CanonicalDocument(
        schema_version=schema_version,
        document_id=document_id,
        source=source,
        status=status,
        page_count=inspection.page_count,
        pages=sorted(pages, key=lambda page: page.page),
        summary=DocumentSummary(
            element_counts=element_counts,
            route_counts=route_counts,
            failed_pages=sorted(set(failed_pages)),
            scanned_pages=sorted(set(scanned_pages)),
            duration_ms=duration_ms,
        ),
    )


def resolve_page_range(
    page_count: int,
    page_start: int | None,
    page_end: int | None,
) -> tuple[int, int]:
    start = 1 if page_start is None else page_start
    end = page_count if page_end is None else page_end
    return start, end
