from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.execution.executor import ExtractionExecutor, GroupRun
from app.grouping.planner import GroupPlanner
from app.merge.combiner import combine_pages
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
from app.models.routing import ExtractionGroup, ExtractionTask, PagePlan
from app.routing.policy import RoutingPolicy
from app.services.extraction_service import ExtractionService
from app.services.job_service import JobService
from app.storage.jobs import JobStore
from app.storage.workspace import WorkspaceManager


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values = {
        "extraction_output_dir": tmp_path / "output",
        "extraction_database_path": tmp_path / "data" / "jobs.db",
        "docling_max_pages_per_group": 30,
        "gemini_target_pages_per_group": 5,
        "gemini_max_pages_per_group": 10,
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
    complex_table: bool = False,
    characters: int = 200,
    printable: float = 1.0,
    formula: int = 0,
    continuity: ContinuitySignals | None = None,
) -> PageInspection:
    return PageInspection(
        page=number,
        width=612,
        height=792,
        text=_text(characters=characters, printable=printable),
        layout=LayoutSignals(formula_like_regions=formula, table_candidate_count=2 if complex_table else 0),
        probable_scan=scan,
        probable_complex_table=complex_table,
        use_pymupdf_fast_path=fast_path,
        continuity=continuity or ContinuitySignals(),
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
    text: str,
    *,
    top: float,
    reading_order: int = 1,
    profile: str | None = None,
) -> CanonicalElement:
    return CanonicalElement(
        element_id=f"{extractor}-{reading_order}",
        type=element_type,
        page=1,
        reading_order=reading_order,
        text=text,
        bbox=BoundingBox(left=72, top=top, right=400, bottom=top + 20),
        extractor=ExtractorProvenance(name=extractor, profile=profile),
    )


def _canonical_page(*elements: CanonicalElement, extractor: str) -> CanonicalPage:
    return CanonicalPage(
        page=1,
        width=612,
        height=792,
        primary_route=extractor,
        extraction_routes=[extractor],
        elements=list(elements),
        attempts=[
            ExtractionAttempt(attempt=1, extractor=extractor, status="completed", element_count=len(elements))
        ],
    )


class RecordingAdapter:
    def __init__(self, name: str, page: CanonicalPage | None = None, *, fail: bool = False) -> None:
        self.name = name
        self.calls: list[dict] = []
        self._page = page
        self._fail = fail

    async def extract(self, pdf_path, pages, tasks, context_pages=None):
        self.calls.append(
            {"pages": list(pages), "context_pages": list(context_pages or []), "tasks": list(tasks)}
        )
        if self._fail:
            raise RuntimeError(f"{self.name} failed")
        page = self._page or CanonicalPage(
            page=pages[0],
            width=612,
            height=792,
            primary_route=self.name,
            extraction_routes=[self.name],
            elements=[],
            attempts=[ExtractionAttempt(attempt=1, extractor=self.name, status="completed")],
        )
        return CanonicalExtractionResult(pages=[page], attempts=page.attempts)


def test_privacy_never_selects_gemini(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    router = RoutingPolicy(settings)
    inspection = _inspection(_page(1, scan=True), _page(2, characters=40, printable=0.5))
    plans = router.create_plans(
        inspection,
        ExtractionPolicy(allow_managed_apis=False),
        document_id="doc",
        gemini_ready=True,
    )
    extractors = {task.extractor for plan in plans for task in plan.tasks}
    assert "gemini" not in extractors
    assert plans[0].primary_route == "docling"
    assert plans[0].tasks[0].profile == "private-ocr"
    assert plans[1].primary_route == "docling"
    assert plans[1].tasks[0].profile == "digital-layout"


def test_fast_path_uses_pymupdf_only(tmp_path: Path) -> None:
    router = RoutingPolicy(_settings(tmp_path))
    plan = router.plan_page(
        _page(1, fast_path=True, complex_table=True),
        ExtractionPolicy(),
        document_id="doc",
        gemini_ready=True,
    )
    assert plan.primary_route == "pymupdf"
    assert [task.extractor for task in plan.tasks] == ["pymupdf"]


def test_complex_table_page_gets_layered_tasks(tmp_path: Path) -> None:
    router = RoutingPolicy(_settings(tmp_path))
    grouper = GroupPlanner(_settings(tmp_path))
    inspection = _inspection(_page(1, complex_table=True))
    plans = router.create_plans(
        inspection,
        ExtractionPolicy(allow_managed_apis=False),
        document_id="doc",
        gemini_ready=False,
    )
    assert [task.extractor for task in plans[0].tasks] == ["pymupdf", "docling"]
    assert plans[0].tasks[1].profile == "digital-table"
    groups = grouper.create_groups(plans, document_id="doc", inspection=inspection)
    extractors = {group.extractor for group in groups}
    assert extractors == {"pymupdf", "docling"}
    assert all(group.pages == [1] for group in groups)


def test_consecutive_pages_split_on_docling_batch_limit(tmp_path: Path) -> None:
    settings = _settings(tmp_path, docling_max_pages_per_group=2)
    router = RoutingPolicy(settings)
    grouper = GroupPlanner(settings)
    inspection = _inspection(
        _page(1, scan=True),
        _page(2, scan=True),
        _page(3, scan=True),
        _page(5, scan=True),
    )
    plans = router.create_plans(
        inspection,
        ExtractionPolicy(allow_managed_apis=False),
        document_id="doc",
        gemini_ready=False,
    )
    groups = grouper.create_groups(plans, document_id="doc", inspection=inspection)
    page_sets = sorted(tuple(group.pages) for group in groups)
    assert page_sets == [(1, 2), (3,), (5,)]


def test_context_pages_are_recorded_not_extracted(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    grouper = GroupPlanner(settings)
    plans = [
        PagePlan(
            page=1,
            primary_route="gemini",
            tasks=[
                ExtractionTask(
                    document_id="doc",
                    page=1,
                    kind="ocr",
                    extractor="gemini",
                    options_hash="uncertain",
                )
            ],
        ),
        PagePlan(
            page=2,
            primary_route="gemini",
            tasks=[
                ExtractionTask(
                    document_id="doc",
                    page=2,
                    kind="ocr",
                    extractor="gemini",
                    options_hash="uncertain",
                )
            ],
        ),
    ]
    inspection = _inspection(
        _page(1, continuity=ContinuitySignals(table_continues_to_next=True)),
        _page(2),
    )
    groups = grouper.create_groups(plans, document_id="doc", inspection=inspection)
    by_page = {tuple(group.pages): group for group in groups}
    assert by_page[(1,)].context_pages == [2]
    assert by_page[(2,)].context_pages == []
    assert 2 not in by_page[(1,)].pages


def test_combiner_keeps_paragraphs_and_prefers_docling_tables() -> None:
    plan = PagePlan(
        page=1,
        primary_route="pymupdf",
        tasks=[
            ExtractionTask(page=1, kind="native_text", extractor="pymupdf"),
            ExtractionTask(page=1, kind="table_structure", extractor="docling", profile="digital-table"),
        ],
        reasons=["Native text layer is usable", "Complex digital table routed to Docling"],
    )
    pymupdf_page = _canonical_page(
        _element("pymupdf", ElementType.PARAGRAPH, "Intro paragraph", top=80, reading_order=1),
        _element("pymupdf", ElementType.TABLE, "weak table", top=200, reading_order=2),
        extractor="pymupdf",
    )
    docling_page = _canonical_page(
        _element(
            "docling",
            ElementType.TABLE,
            "structured table",
            top=200,
            reading_order=1,
            profile="digital-table",
        ),
        extractor="docling",
    )
    inspection = _inspection(_page(1, complex_table=True))
    combined = combine_pages(
        inspection,
        [plan],
        [
            GroupRun(
                group=ExtractionGroup(
                    group_id="pymupdf-native_text-0001",
                    document_id="doc",
                    extractor="pymupdf",
                    kind="native_text",
                    pages=[1],
                ),
                result=CanonicalExtractionResult(pages=[pymupdf_page]),
            ),
            GroupRun(
                group=ExtractionGroup(
                    group_id="docling-table_structure-0002",
                    document_id="doc",
                    extractor="docling",
                    profile="digital-table",
                    kind="table_structure",
                    pages=[1],
                ),
                result=CanonicalExtractionResult(pages=[docling_page]),
            ),
        ],
    )
    page = combined[0]
    types = [element.type for element in page.elements]
    texts = [element.text for element in page.elements]
    assert ElementType.PARAGRAPH in types
    assert ElementType.TABLE in types
    assert "Intro paragraph" in texts
    assert "structured table" in texts
    assert "weak table" not in texts
    assert page.primary_route == "pymupdf"
    assert set(page.extraction_routes) == {"pymupdf", "docling"}


@pytest.mark.asyncio
async def test_layered_page_runs_two_groups_through_executor(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    pymupdf_page = _canonical_page(
        _element("pymupdf", ElementType.PARAGRAPH, "Body text", top=80),
        extractor="pymupdf",
    )
    docling_page = _canonical_page(
        _element("docling", ElementType.TABLE, "Grid", top=180, profile="digital-table"),
        extractor="docling",
    )
    pymupdf = RecordingAdapter("pymupdf", pymupdf_page)
    docling = RecordingAdapter("docling", docling_page)
    service = ExtractionService(
        job_service=JobService(JobStore(settings)),
        settings=settings,
        inspector=object(),  # type: ignore[arg-type]
        pymupdf_adapter=pymupdf,  # type: ignore[arg-type]
        docling_adapter=docling,  # type: ignore[arg-type]
        workspace_manager=WorkspaceManager(settings),
        executor=ExtractionExecutor(settings, pymupdf, docling),  # type: ignore[arg-type]
    )
    inspection = _inspection(_page(1, complex_table=True))
    outcome = await service._extract_pages(
        pdf_path=pdf_path,
        inspection=inspection,
        force_extractor=None,
        allow_managed_apis=False,
    )
    assert len(pymupdf.calls) == 1
    assert len(docling.calls) == 1
    assert pymupdf.calls[0]["pages"] == [1]
    assert docling.calls[0]["pages"] == [1]
    assert {group.extractor for group in outcome.groups} == {"pymupdf", "docling"}
    assert outcome.pages[0].primary_route == "pymupdf"
    assert {element.type for element in outcome.pages[0].elements} == {
        ElementType.PARAGRAPH,
        ElementType.TABLE,
    }


@pytest.mark.asyncio
async def test_failed_group_does_not_cancel_other_groups(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    pymupdf = RecordingAdapter(
        "pymupdf",
        _canonical_page(_element("pymupdf", ElementType.PARAGRAPH, "kept", top=80), extractor="pymupdf"),
    )
    docling = RecordingAdapter("docling", fail=True)
    executor = ExtractionExecutor(settings, pymupdf, docling)  # type: ignore[arg-type]
    groups = [
        ExtractionGroup(
            group_id="pymupdf-native_text-0001",
            document_id="doc",
            extractor="pymupdf",
            kind="native_text",
            pages=[1],
            tasks=[ExtractionTask(page=1, kind="native_text", extractor="pymupdf")],
        ),
        ExtractionGroup(
            group_id="docling-table_structure-0002",
            document_id="doc",
            extractor="docling",
            profile="digital-table",
            kind="table_structure",
            pages=[1],
            tasks=[ExtractionTask(page=1, kind="table_structure", extractor="docling")],
        ),
    ]
    runs = await executor.run(pdf_path, groups)
    assert any(run.result is not None and run.group.extractor == "pymupdf" for run in runs)
    assert any(run.error is not None and run.group.extractor == "docling" for run in runs)
    assert pymupdf.calls


@pytest.mark.asyncio
async def test_executor_passes_context_pages_without_extracting_them(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    adapter = RecordingAdapter(
        "docling",
        CanonicalPage(
            page=1,
            width=612,
            height=792,
            primary_route="docling",
            extraction_routes=["docling"],
            elements=[],
            attempts=[ExtractionAttempt(attempt=1, extractor="docling", status="completed")],
        ),
    )
    executor = ExtractionExecutor(settings, RecordingAdapter("pymupdf"), adapter)  # type: ignore[arg-type]
    runs = await executor.run(
        pdf_path,
        [
            ExtractionGroup(
                group_id="docling-table_structure-0001",
                document_id="doc",
                extractor="docling",
                profile="digital-table",
                kind="table_structure",
                pages=[1],
                context_pages=[2],
                tasks=[ExtractionTask(page=1, kind="table_structure", extractor="docling")],
            )
        ],
    )
    assert adapter.calls[0]["pages"] == [1]
    assert adapter.calls[0]["context_pages"] == [2]
    assert runs[0].result is not None
    assert [page.page for page in runs[0].result.pages] == [1]
