from __future__ import annotations

import io
import json
from pathlib import Path

import fitz
import pytest

from app.adapters.groq_client import GroqCompletion
from app.adapters.groq_vision_adapter import GroqVisionAdapter
from app.adapters.pymupdf_adapter import PyMuPDFAdapter
from app.config import Settings
from app.execution.executor import ExtractionExecutor
from app.fallback.manager import FallbackManager
from app.fallback.policy import select_fallback
from app.grouping.planner import GroupPlanner
from app.inspection.pdf_inspector import PdfInspector
from app.merge.merger import finalize_pages
from app.models.canonical import (
    BoundingBox,
    CanonicalElement,
    CanonicalExtractionResult,
    CanonicalPage,
    ElementType,
    ExtractionAttempt,
    ExtractorProvenance,
)
from app.models.inspection import (
    ContinuitySignals,
    DocumentInspection,
    LayoutSignals,
    PageInspection,
    TextSignals,
)
from app.models.jobs import ExtractionPolicy
from app.models.routing import ExtractionTask
from app.models.validation import ValidationFailure, ValidationResult
from app.routing.policy import RoutingPolicy
from app.services.extraction_service import ExtractionService
from app.services.job_service import JobService
from app.storage.jobs import JobStore
from app.storage.workspace import WorkspaceManager
from app.validation.validator import PageValidator


FIGURE_REGION = [100.0, 220.0, 500.0, 460.0]


class FakeGroqCompleter:
    def __init__(self, payloads: str | list[str]) -> None:
        self.payloads = [payloads] if isinstance(payloads, str) else list(payloads)
        self.calls: list[dict] = []

    async def complete(self, *, model: str, messages: list[dict], timeout_seconds: int) -> GroqCompletion:
        self.calls.append(
            {"model": model, "messages": messages, "timeout_seconds": timeout_seconds}
        )
        index = min(len(self.calls) - 1, len(self.payloads) - 1)
        return GroqCompletion(
            content=self.payloads[index],
            model=model,
            finish_reason="stop",
            prompt_tokens=7,
            completion_tokens=13,
            total_tokens=20,
        )


class RecordingAdapter:
    def __init__(self, name: str, page: CanonicalPage | None = None, *, fail: bool = False) -> None:
        self.name = name
        self.calls: list[dict] = []
        self._page = page
        self._fail = fail

    async def extract(self, pdf_path, pages, tasks, context_pages=None):
        self.calls.append({"pages": list(pages), "tasks": list(tasks), "context_pages": context_pages})
        if self._fail:
            raise RuntimeError(f"{self.name} failed")
        page = self._page or CanonicalPage(
            page=pages[0],
            width=612,
            height=792,
            primary_route=self.name,
            extraction_routes=[self.name],
            attempts=[ExtractionAttempt(attempt=1, extractor=self.name, status="completed")],
        )
        return CanonicalExtractionResult(pages=[page], attempts=page.attempts)


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values = {
        "extraction_output_dir": tmp_path / "output",
        "extraction_database_path": tmp_path / "data" / "jobs.db",
        "groq_visual_extraction_enabled": True,
        "groq_api_key": "test-groq-key",
        "gemini_retry_backoff_seconds": 0.0,
    }
    values.update(overrides)
    return Settings(**values)


def _text(*, characters: int = 200, printable: float = 1.0) -> TextSignals:
    return TextSignals(
        character_count=characters,
        printable_ratio=printable,
        replacement_character_ratio=0.0,
    )


def _page(
    number: int,
    *,
    scan: bool = False,
    fast_path: bool = False,
    figure_regions: list[list[float]] | None = None,
    characters: int = 200,
) -> PageInspection:
    return PageInspection(
        page=number,
        width=612,
        height=792,
        text=_text(characters=characters),
        layout=LayoutSignals(figure_candidate_count=1 if figure_regions else 0),
        probable_scan=scan,
        use_pymupdf_fast_path=fast_path,
        figure_regions=figure_regions or [],
        continuity=ContinuitySignals(),
    )


def _inspection(*pages: PageInspection, document_id: str = "doc") -> DocumentInspection:
    return DocumentInspection(
        schema_version="1.0",
        document_id=document_id,
        page_count=len(pages),
        pages=list(pages),
    )


def _element(
    extractor: str,
    element_type: ElementType,
    text: str | None,
    *,
    page: int = 1,
    left: float = 100,
    top: float = 220,
    right: float = 500,
    bottom: float = 460,
    reading_order: int = 1,
    asset: str | None = None,
) -> CanonicalElement:
    return CanonicalElement(
        element_id=f"{extractor}-{reading_order}",
        type=element_type,
        page=page,
        reading_order=reading_order,
        text=text,
        bbox=BoundingBox(left=left, top=top, right=right, bottom=bottom),
        asset=asset,
        extractor=ExtractorProvenance(name=extractor),
    )


def groq_payload(*, description: str = "Bar chart of quarterly revenue by region.") -> str:
    return json.dumps(
        {
            "type": "chart",
            "title": "Revenue by region",
            "description": description,
            "caption": "Figure 1. Revenue by region.",
            "uncertain": False,
        }
    )


def make_figure_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    paragraph = (
        "This dense digital paragraph keeps the page from being classified as a scan. "
        * 8
    )
    for line_index, chunk_start in enumerate(range(0, len(paragraph), 90)):
        page.insert_text((72, 36 + (line_index * 12)), paragraph[chunk_start : chunk_start + 90], fontsize=10)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 120), 0)
    pix.clear_with(160)
    page.insert_image(fitz.Rect(100, 220, 500, 460), pixmap=pix)
    page.insert_text((100, 480), "Figure 1. Revenue by region.", fontsize=10)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def _workspace_pdf(tmp_path: Path, pdf_bytes: bytes) -> Path:
    workspace = tmp_path / "doc-workspace"
    (workspace / "raw").mkdir(parents=True)
    (workspace / "assets" / "pictures").mkdir(parents=True)
    (workspace / "assets" / "charts").mkdir(parents=True)
    pdf_path = workspace / "source.pdf"
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def test_visual_tasks_require_opt_in_and_ops_switch(tmp_path: Path) -> None:
    page = _page(1, fast_path=True, figure_regions=[FIGURE_REGION])
    enabled = RoutingPolicy(_settings(tmp_path))
    plan = enabled.plan_page(
        page,
        ExtractionPolicy(visual_understanding=True, allow_managed_apis=True),
        document_id="doc",
        gemini_ready=False,
        groq_ready=True,
    )
    assert [task.extractor for task in plan.tasks] == ["pymupdf", "groq-vision"]
    assert plan.tasks[1].kind == "visual_understanding"
    assert plan.tasks[1].region == FIGURE_REGION
    assert plan.primary_route == "pymupdf"

    disabled = RoutingPolicy(_settings(tmp_path, groq_visual_extraction_enabled=False))
    off = disabled.plan_page(
        page,
        ExtractionPolicy(visual_understanding=True, allow_managed_apis=True),
        document_id="doc",
        gemini_ready=False,
        groq_ready=True,
    )
    assert [task.extractor for task in off.tasks] == ["pymupdf"]

    no_opt_in = enabled.plan_page(
        page,
        ExtractionPolicy(visual_understanding=False, allow_managed_apis=True),
        document_id="doc",
        gemini_ready=False,
        groq_ready=True,
    )
    assert [task.extractor for task in no_opt_in.tasks] == ["pymupdf"]


def test_privacy_never_selects_groq(tmp_path: Path) -> None:
    router = RoutingPolicy(_settings(tmp_path))
    plan = router.plan_page(
        _page(1, fast_path=True, figure_regions=[FIGURE_REGION]),
        ExtractionPolicy(visual_understanding=True, allow_managed_apis=False),
        document_id="doc",
        gemini_ready=True,
        groq_ready=True,
    )
    assert "groq-vision" not in {task.extractor for task in plan.tasks}


def test_forced_groq_is_blocked_without_managed_apis(tmp_path: Path) -> None:
    router = RoutingPolicy(_settings(tmp_path))
    plan = router.plan_page(
        _page(1, figure_regions=[FIGURE_REGION]),
        ExtractionPolicy(force_extractor="groq-vision", allow_managed_apis=False),
        document_id="doc",
        gemini_ready=False,
        groq_ready=True,
    )
    assert plan.tasks == []
    assert plan.primary_route is None
    assert any("prohibited" in reason.lower() for reason in plan.reasons)


def test_visual_groups_are_region_sized(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    router = RoutingPolicy(settings)
    grouper = GroupPlanner(settings)
    inspection = _inspection(
        _page(1, fast_path=True, figure_regions=[FIGURE_REGION]),
        _page(2, fast_path=True, figure_regions=[[80.0, 100.0, 400.0, 300.0]]),
    )
    plans = router.create_plans(
        inspection,
        ExtractionPolicy(visual_understanding=True, allow_managed_apis=True),
        document_id="doc",
        gemini_ready=False,
        groq_ready=True,
    )
    groups = grouper.create_groups(plans, document_id="doc", inspection=inspection)
    groq_groups = [group for group in groups if group.extractor == "groq-vision"]
    assert len(groq_groups) == 2
    assert all(len(group.pages) == 1 for group in groq_groups)


@pytest.mark.asyncio
async def test_groq_adapter_writes_crop_and_grounded_description(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pdf_path = _workspace_pdf(tmp_path, make_figure_pdf_bytes())
    completer = FakeGroqCompleter(groq_payload())
    adapter = GroqVisionAdapter(settings, completer=completer)
    result = await adapter.extract(
        pdf_path,
        [1],
        [
            ExtractionTask(
                page=1,
                kind="visual_understanding",
                extractor="groq-vision",
                region=FIGURE_REGION,
            )
        ],
    )
    assert completer.calls
    page = result.pages[0]
    assert page.elements[0].type == ElementType.CHART
    assert page.elements[0].text == "Bar chart of quarterly revenue by region."
    assert page.elements[0].asset
    crop = pdf_path.parent / page.elements[0].asset
    assert crop.is_file()
    assert crop.stat().st_size > 0
    raw = pdf_path.parent / "raw" / "groq-page-1-r220.json"
    assert raw.is_file()


def test_merger_attaches_groq_text_to_existing_picture() -> None:
    page = CanonicalPage(
        page=1,
        width=612,
        height=792,
        primary_route="pymupdf",
        extraction_routes=["pymupdf", "groq-vision"],
        elements=[
            _element("pymupdf", ElementType.PARAGRAPH, "Intro paragraph about revenue.", top=40, bottom=70, reading_order=1),
            _element("pymupdf", ElementType.PICTURE, None, reading_order=2, asset="assets/pictures/page_1_picture_1.png"),
            _element(
                "groq-vision",
                ElementType.CHART,
                "Bar chart of quarterly revenue by region.",
                reading_order=3,
                asset="assets/charts/page_1_r1.png",
            ),
        ],
    )
    merged = finalize_pages([page], _inspection(_page(1, figure_regions=[FIGURE_REGION])))[0]
    pictures = [element for element in merged.elements if element.type in {ElementType.PICTURE, ElementType.CHART}]
    texts = [element.text for element in merged.elements]
    assert "Intro paragraph about revenue." in texts
    assert len(pictures) == 1
    assert pictures[0].type == ElementType.CHART
    assert pictures[0].text == "Bar chart of quarterly revenue by region."
    assert pictures[0].metadata["visual_semantics"]["extractor"] == "groq-vision"


def test_visual_meaning_missing_selects_groq_when_enabled() -> None:
    page = CanonicalPage(
        page=1,
        width=612,
        height=792,
        primary_route="pymupdf",
        extraction_routes=["pymupdf"],
        elements=[_element("pymupdf", ElementType.CHART, None, asset="assets/pictures/page_1_picture_1.png")],
        attempts=[ExtractionAttempt(attempt=1, extractor="pymupdf", status="completed")],
    )
    validation = ValidationResult(
        page=1,
        confidence=0.95,
        passed=True,
        failures=[ValidationFailure(code="VISUAL_MEANING_MISSING", message="no description")],
    )
    choice = select_fallback(
        page,
        validation,
        ExtractionPolicy(visual_understanding=True, allow_managed_apis=True),
        gemini_ready=False,
        groq_ready=True,
        max_attempts=3,
    )
    assert choice is not None
    assert choice.extractor == "groq-vision"
    assert choice.reason_code == "VISUAL_MEANING_MISSING"
    assert choice.regions == ((100.0, 220.0, 500.0, 460.0),)


def test_visual_fallback_respects_privacy_and_opt_in() -> None:
    page = CanonicalPage(
        page=1,
        width=612,
        height=792,
        elements=[_element("pymupdf", ElementType.CHART, None)],
        attempts=[ExtractionAttempt(attempt=1, extractor="pymupdf", status="completed")],
    )
    validation = ValidationResult(
        page=1,
        confidence=0.95,
        passed=True,
        failures=[ValidationFailure(code="VISUAL_MEANING_MISSING", message="no description")],
    )
    assert (
        select_fallback(
            page,
            validation,
            ExtractionPolicy(visual_understanding=True, allow_managed_apis=False),
            gemini_ready=True,
            groq_ready=True,
            max_attempts=3,
        )
        is None
    )
    assert (
        select_fallback(
            page,
            validation,
            ExtractionPolicy(visual_understanding=False, allow_managed_apis=True),
            gemini_ready=True,
            groq_ready=True,
            max_attempts=3,
        )
        is None
    )


@pytest.mark.asyncio
async def test_fallback_attaches_groq_without_replacing_page(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    groq_page = CanonicalPage(
        page=1,
        width=612,
        height=792,
        primary_route="groq-vision",
        extraction_routes=["groq-vision"],
        elements=[
            _element("groq-vision", ElementType.CHART, "Bar chart of quarterly revenue by region."),
        ],
        attempts=[ExtractionAttempt(attempt=1, extractor="groq-vision", status="completed")],
    )
    groq = RecordingAdapter("groq-vision", groq_page)
    manager = FallbackManager(
        settings,
        ExtractionExecutor(settings, RecordingAdapter("pymupdf"), RecordingAdapter("docling"), None, groq),  # type: ignore[arg-type]
        PageValidator(settings),
    )
    original = CanonicalPage(
        page=1,
        width=612,
        height=792,
        primary_route="pymupdf",
        extraction_routes=["pymupdf"],
        elements=[
            _element("pymupdf", ElementType.PARAGRAPH, "Intro paragraph about revenue.", top=40, bottom=70, reading_order=1),
            _element("pymupdf", ElementType.CHART, None, reading_order=2, asset="assets/pictures/page_1_picture_1.png"),
        ],
        attempts=[ExtractionAttempt(attempt=1, extractor="pymupdf", status="completed")],
    )
    resolution = await manager.resolve(
        pdf_path,
        [original],
        [
            ValidationResult(
                page=1,
                confidence=0.95,
                passed=True,
                failures=[ValidationFailure(code="VISUAL_MEANING_MISSING", message="no description")],
            )
        ],
        _inspection(_page(1, figure_regions=[FIGURE_REGION])),
        ExtractionPolicy(visual_understanding=True, allow_managed_apis=True),
        document_id="doc",
        gemini_ready=False,
        groq_ready=True,
    )
    assert groq.calls
    assert groq.calls[0]["pages"] == [1]
    assert groq.calls[0]["tasks"][0].region == FIGURE_REGION
    page = resolution.pages[0]
    assert page.primary_route == "pymupdf"
    texts = [element.text for element in page.elements]
    assert "Intro paragraph about revenue." in texts
    charts = [element for element in page.elements if element.type == ElementType.CHART]
    assert charts[0].text == "Bar chart of quarterly revenue by region."
    assert resolution.records[0].to_extractor == "groq-vision"


@pytest.mark.asyncio
async def test_service_attaches_groq_when_visual_understanding_enabled(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pdf_path = _workspace_pdf(tmp_path, make_figure_pdf_bytes())
    completer = FakeGroqCompleter(groq_payload())
    groq = GroqVisionAdapter(settings, completer=completer)
    service = ExtractionService(
        job_service=JobService(JobStore(settings)),
        settings=settings,
        inspector=PdfInspector(settings),
        pymupdf_adapter=PyMuPDFAdapter(settings),
        docling_adapter=RecordingAdapter("docling"),  # type: ignore[arg-type]
        workspace_manager=WorkspaceManager(settings),
        groq_adapter=groq,
    )
    inspection = PdfInspector(settings).inspect(pdf_path, document_id="doc")
    assert inspection.pages[0].figure_regions
    outcome = await service._extract_pages(
        pdf_path=pdf_path,
        inspection=inspection,
        force_extractor=None,
        allow_managed_apis=True,
        visual_understanding=True,
    )
    assert completer.calls
    assert "groq-vision" in {group.extractor for group in outcome.groups}
    texts = [element.text for element in outcome.pages[0].elements]
    assert any(text and "quarterly revenue" in text.lower() for text in texts)
    assert any(
        element.type in {ElementType.PICTURE, ElementType.CHART} and element.text
        for element in outcome.pages[0].elements
    )
    assert any(
        element.type == ElementType.PARAGRAPH and element.text
        for element in outcome.pages[0].elements
    )


@pytest.mark.asyncio
async def test_default_path_does_not_call_groq(tmp_path: Path) -> None:
    settings = _settings(tmp_path, groq_visual_extraction_enabled=False)
    pdf_path = _workspace_pdf(tmp_path, make_figure_pdf_bytes())
    completer = FakeGroqCompleter(groq_payload())
    groq = GroqVisionAdapter(settings, completer=completer)
    service = ExtractionService(
        job_service=JobService(JobStore(settings)),
        settings=settings,
        inspector=PdfInspector(settings),
        pymupdf_adapter=PyMuPDFAdapter(settings),
        docling_adapter=RecordingAdapter("docling"),  # type: ignore[arg-type]
        workspace_manager=WorkspaceManager(settings),
        groq_adapter=groq,
    )
    inspection = PdfInspector(settings).inspect(pdf_path, document_id="doc")
    outcome = await service._extract_pages(
        pdf_path=pdf_path,
        inspection=inspection,
        force_extractor=None,
        allow_managed_apis=True,
        visual_understanding=True,
    )
    assert completer.calls == []
    assert "groq-vision" not in {group.extractor for group in outcome.groups}

    enabled = _settings(tmp_path)
    enabled_service = ExtractionService(
        job_service=JobService(JobStore(enabled)),
        settings=enabled,
        inspector=PdfInspector(enabled),
        pymupdf_adapter=PyMuPDFAdapter(enabled),
        docling_adapter=RecordingAdapter("docling"),  # type: ignore[arg-type]
        workspace_manager=WorkspaceManager(enabled),
        groq_adapter=GroqVisionAdapter(enabled, completer=completer),
    )
    skipped = await enabled_service._extract_pages(
        pdf_path=pdf_path,
        inspection=inspection,
        force_extractor=None,
        allow_managed_apis=True,
        visual_understanding=False,
    )
    assert completer.calls == []
    assert "groq-vision" not in {group.extractor for group in skipped.groups}
