from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.execution.executor import ExtractionExecutor
from app.fallback.manager import FallbackManager
from app.fallback.policy import select_fallback
from app.merge.coordinates import normalize_bbox
from app.merge.merger import finalize_pages
from app.models.canonical import (
    BoundingBox,
    CanonicalElement,
    CanonicalExtractionResult,
    CanonicalPage,
    ElementType,
    ExtractionAttempt,
    ExtractionError,
    ExtractorProvenance,
)
from app.models.inspection import DocumentInspection, PageInspection, TextSignals
from app.models.jobs import ExtractionPolicy
from app.models.validation import ValidationFailure, ValidationResult
from app.validation.validator import PageValidator


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values = {
        "extraction_output_dir": tmp_path / "output",
        "extraction_database_path": tmp_path / "data" / "jobs.db",
        "extraction_max_attempts_per_page": 3,
        "gemini_retry_backoff_seconds": 0.0,
    }
    values.update(overrides)
    return Settings(**values)


def _element(
    extractor: str,
    element_type: ElementType,
    text: str,
    *,
    page: int = 1,
    top: float = 80,
    left: float = 72,
    right: float = 400,
    bottom: float | None = None,
    reading_order: int = 1,
    profile: str | None = None,
) -> CanonicalElement:
    return CanonicalElement(
        element_id=f"{extractor}-{reading_order}",
        type=element_type,
        page=page,
        reading_order=reading_order,
        text=text,
        bbox=BoundingBox(left=left, top=top, right=right, bottom=bottom if bottom is not None else top + 40),
        extractor=ExtractorProvenance(name=extractor, profile=profile),
    )


def _page(
    number: int,
    *elements: CanonicalElement,
    extractor: str = "pymupdf",
    errors: list[ExtractionError] | None = None,
    attempts: int = 1,
) -> CanonicalPage:
    return CanonicalPage(
        page=number,
        width=612,
        height=792,
        primary_route=extractor,
        extraction_routes=[extractor],
        elements=list(elements),
        errors=list(errors or []),
        attempts=[
            ExtractionAttempt(
                attempt=index,
                extractor=extractor,
                status="completed",
                element_count=len(elements),
            )
            for index in range(1, attempts + 1)
        ],
    )


def _inspection(*numbers: int, document_id: str = "doc") -> DocumentInspection:
    return DocumentInspection(
        schema_version="1.0",
        document_id=document_id,
        page_count=len(numbers),
        pages=[
            PageInspection(
                page=number,
                width=612,
                height=792,
                text=TextSignals(character_count=200, printable_ratio=1.0),
            )
            for number in numbers
        ],
    )


class RecordingAdapter:
    def __init__(self, name: str, text: str = "Recovered fallback text with enough characters.", *, fail: bool = False, profile: str | None = None) -> None:
        self.name = name
        self.calls: list[list[int]] = []
        self._text = text
        self._fail = fail
        self._profile = profile

    async def extract(self, pdf_path, pages, tasks, context_pages=None):
        self.calls.append(list(pages))
        if self._fail:
            raise RuntimeError(f"{self.name} failed")
        page_number = pages[0]
        element = _element(self.name, ElementType.PARAGRAPH, self._text, page=page_number, profile=self._profile)
        page = CanonicalPage(
            page=page_number,
            width=612,
            height=792,
            primary_route=self.name,
            extraction_routes=[self.name],
            elements=[element],
            attempts=[
                ExtractionAttempt(
                    attempt=1,
                    extractor=self.name,
                    profile=self._profile,
                    status="completed",
                    element_count=1,
                )
            ],
        )
        return CanonicalExtractionResult(pages=[page], attempts=page.attempts)


def test_native_text_corrupt_selects_gemini_when_managed_allowed() -> None:
    page = _page(
        1,
        _element("pymupdf", ElementType.PARAGRAPH, "\ufffd" * 40),
        errors=[ExtractionError(code="NATIVE_TEXT_CORRUPT", message="corrupt", page=1)],
    )
    validation = ValidationResult(
        page=1,
        confidence=0.6,
        passed=False,
        failures=[ValidationFailure(code="NATIVE_TEXT_CORRUPT", message="corrupt")],
    )
    choice = select_fallback(
        page,
        validation,
        ExtractionPolicy(allow_managed_apis=True),
        gemini_ready=True,
        max_attempts=3,
    )
    assert choice is not None
    assert choice.extractor == "gemini"
    assert choice.reason_code == "NATIVE_TEXT_CORRUPT"


def test_privacy_rewrites_gemini_fallback_to_private_ocr() -> None:
    page = _page(
        1,
        errors=[ExtractionError(code="NATIVE_TEXT_CORRUPT", message="corrupt", page=1)],
    )
    validation = ValidationResult(
        page=1,
        confidence=0.6,
        passed=False,
        failures=[ValidationFailure(code="NATIVE_TEXT_CORRUPT", message="corrupt")],
    )
    choice = select_fallback(
        page,
        validation,
        ExtractionPolicy(allow_managed_apis=False),
        gemini_ready=True,
        max_attempts=3,
    )
    assert choice is not None
    assert choice.extractor == "docling"
    assert choice.profile == "private-ocr"


def test_force_extractor_skips_fallback() -> None:
    page = _page(
        1,
        errors=[ExtractionError(code="NATIVE_TEXT_CORRUPT", message="corrupt", page=1)],
    )
    validation = ValidationResult(
        page=1,
        confidence=0.6,
        passed=False,
        failures=[ValidationFailure(code="NATIVE_TEXT_CORRUPT", message="corrupt")],
    )
    assert (
        select_fallback(
            page,
            validation,
            ExtractionPolicy(force_extractor="pymupdf"),
            gemini_ready=True,
            max_attempts=3,
        )
        is None
    )


def test_attempt_cap_blocks_fallback() -> None:
    page = _page(
        1,
        errors=[ExtractionError(code="NATIVE_TEXT_CORRUPT", message="corrupt", page=1)],
        attempts=3,
    )
    validation = ValidationResult(
        page=1,
        confidence=0.6,
        passed=False,
        failures=[ValidationFailure(code="NATIVE_TEXT_CORRUPT", message="corrupt")],
    )
    assert (
        select_fallback(
            page,
            validation,
            ExtractionPolicy(),
            gemini_ready=True,
            max_attempts=3,
        )
        is None
    )


def test_scanned_unconfigured_pages_are_not_retried() -> None:
    page = CanonicalPage(
        page=1,
        width=612,
        height=792,
        errors=[ExtractionError(code="SCANNED_PAGE_NOT_EXTRACTED", message="skip", page=1)],
    )
    validation = ValidationResult(page=1, confidence=1.0, passed=True, failures=[])
    assert (
        select_fallback(
            page,
            validation,
            ExtractionPolicy(allow_managed_apis=True),
            gemini_ready=False,
            max_attempts=3,
        )
        is None
    )


def test_normalize_bbox_converts_bottom_left_and_clamps() -> None:
    bbox = BoundingBox(
        left=-10,
        top=100,
        right=50,
        bottom=20,
        coordinate_origin="bottom-left",
        unit="pdf-point",
    )
    normalized = normalize_bbox(bbox, 200, 200)
    assert normalized.coordinate_origin == "top-left"
    assert normalized.left == 0
    assert normalized.top == 100
    assert normalized.bottom == 180
    assert normalized.right == 50


def test_merger_drops_table_text_and_keeps_outside_paragraphs() -> None:
    page = _page(
        1,
        _element("pymupdf", ElementType.PARAGRAPH, "Intro paragraph", top=40, bottom=70, reading_order=1),
        _element("pymupdf", ElementType.PARAGRAPH, "Revenue 10", top=210, bottom=240, reading_order=2),
        _element(
            "docling",
            ElementType.TABLE,
            "Revenue 10 Costs 4",
            top=200,
            bottom=320,
            reading_order=3,
            profile="digital-table",
        ),
    )
    merged = finalize_pages([page], _inspection(1))[0]
    texts = [element.text for element in merged.elements]
    types = [element.type for element in merged.elements]
    assert "Intro paragraph" in texts
    assert ElementType.TABLE in types
    assert "Revenue 10" not in texts
    assert merged.elements[0].element_id == "doc:p1:e1"
    assert any("duplicate table text" in warning for warning in merged.warnings)


def test_failed_page_does_not_discard_successful_page() -> None:
    good = _page(1, _element("pymupdf", ElementType.PARAGRAPH, "Kept page", page=1))
    failed = _page(
        2,
        errors=[ExtractionError(code="PYMUPDF_EXTRACTION_FAILED", message="boom", page=2)],
    )
    failed.elements = []
    merged = finalize_pages([good, failed], _inspection(1, 2))
    assert merged[0].elements[0].text == "Kept page"
    assert merged[1].page == 2
    assert merged[1].errors


@pytest.mark.asyncio
async def test_fallback_retries_only_the_failed_page(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    gemini = RecordingAdapter("gemini", "Recovered by Gemini with enough useful characters.")
    docling = RecordingAdapter("docling", fail=True)
    pymupdf = RecordingAdapter("pymupdf")
    manager = FallbackManager(
        settings,
        ExtractionExecutor(settings, pymupdf, docling, gemini),  # type: ignore[arg-type]
        PageValidator(settings),
    )
    pages = [
        _page(1, _element("pymupdf", ElementType.PARAGRAPH, "Healthy page of extracted native text.", page=1)),
        _page(
            2,
            _element("pymupdf", ElementType.PARAGRAPH, "\ufffd" * 40, page=2),
            errors=[ExtractionError(code="NATIVE_TEXT_CORRUPT", message="corrupt", page=2)],
        ),
    ]
    validations = [
        ValidationResult(page=1, confidence=1.0, passed=True, failures=[]),
        ValidationResult(
            page=2,
            confidence=0.5,
            passed=False,
            failures=[ValidationFailure(code="NATIVE_TEXT_CORRUPT", message="corrupt")],
        ),
    ]
    resolution = await manager.resolve(
        pdf_path,
        pages,
        validations,
        _inspection(1, 2),
        ExtractionPolicy(allow_managed_apis=True),
        document_id="doc",
        gemini_ready=True,
    )
    assert gemini.calls == [[2]]
    assert pymupdf.calls == []
    assert resolution.pages[0].elements[0].text == "Healthy page of extracted native text."
    assert resolution.pages[1].elements[0].text == "Recovered by Gemini with enough useful characters."
    assert resolution.records[0].status == "completed"
    assert resolution.records[0].to_extractor == "gemini"
    assert resolution.records[0].page == 2
