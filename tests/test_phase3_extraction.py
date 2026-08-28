from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any

import fitz
import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.docling_adapter import DoclingAdapter
from app.adapters.pymupdf_adapter import PyMuPDFAdapter
from app.api.dependencies import (
    get_docling_adapter,
    get_gemini_adapter,
    get_groq_adapter,
    get_job_store,
)
from app.config import Settings, get_settings
from app.inspection.pdf_inspector import PdfInspector
from app.main import create_app
from app.models.canonical import ElementType
from app.models.routing import ExtractionTask
from app.services.extraction_service import ExtractionService
from app.services.job_service import JobService
from app.storage.jobs import JobStore
from app.storage.workspace import WorkspaceManager


class FakeBBox:
    def __init__(self, l: float, t: float, r: float, b: float, origin: str = "TOPLEFT") -> None:
        self.l = l
        self.t = t
        self.r = r
        self.b = b
        self.coord_origin = origin

    def to_top_left_origin(self, page_height: float) -> FakeBBox:
        if "BOTTOM" in self.coord_origin.upper():
            return FakeBBox(self.l, page_height - self.t, self.r, page_height - self.b, "TOPLEFT")
        return self


class FakeProv:
    def __init__(self, page_no: int, bbox: FakeBBox) -> None:
        self.page_no = page_no
        self.bbox = bbox


class FakeItem:
    def __init__(
        self,
        label: str,
        text: str | None,
        page_no: int,
        bbox: FakeBBox,
        markdown: str | None = None,
        html: str | None = None,
    ) -> None:
        self.label = label
        self.text = text
        self.prov = [FakeProv(page_no, bbox)]
        self._markdown = markdown
        self._html = html

    def export_to_markdown(self, **kwargs: Any) -> str | None:
        return self._markdown

    def export_to_html(self, **kwargs: Any) -> str | None:
        return self._html


class FakeDocument:
    def __init__(self, items: list[FakeItem]) -> None:
        self._items = items

    def iterate_items(self):
        for item in self._items:
            yield item, 0

    def save_as_json(self, path: Path) -> None:
        Path(path).write_text("{}", encoding="utf-8")


class FakeConverter:
    def __init__(self, items: list[FakeItem]) -> None:
        self.items = items
        self.sources: list[str] = []

    def convert(self, source: str, **kwargs: Any) -> Any:
        self.sources.append(source)
        return type("ConversionResult", (), {"document": FakeDocument(self.items)})()


def layout_items() -> list[FakeItem]:
    return [
        FakeItem("section_header", "Quarterly Revenue", 1, FakeBBox(72, 60, 400, 90)),
        FakeItem("paragraph", "Revenue grew in North America.", 1, FakeBBox(72, 110, 480, 160)),
    ]


def table_items() -> list[FakeItem]:
    return [
        FakeItem(
            "table",
            "Region Value",
            1,
            FakeBBox(40, 180, 570, 380),
            markdown="| Region | Value |\n| --- | --- |\n| North | 10 |",
            html="<table><tr><td>Region</td><td>Value</td></tr></table>",
        )
    ]


def ocr_items() -> list[FakeItem]:
    return [FakeItem("paragraph", "Local OCR recovered this scan text.", 1, FakeBBox(72, 72, 400, 120))]


def converter_factory_for(items_by_profile: dict[str, list[FakeItem]]):
    converters: dict[str, FakeConverter] = {}

    def factory(profile: str, settings: Settings) -> FakeConverter:
        if profile not in converters:
            converters[profile] = FakeConverter(items_by_profile.get(profile, layout_items()))
        return converters[profile]

    factory.converters = converters  # type: ignore[attr-defined]
    return factory


def make_digital_pdf_bytes(*texts: str) -> bytes:
    document = fitz.open()
    if not texts:
        texts = ("Hello extraction phase three.",)
    for text in texts:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=12)
        page.insert_text((72, 120), "Section Title", fontsize=18)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def make_scanned_like_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 612, 792), 0)
    pix.clear_with(255)
    page.insert_image(page.rect, pixmap=pix)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def make_mixed_pdf_bytes() -> bytes:
    document = fitz.open()
    digital = document.new_page(width=612, height=792)
    paragraph = "Dense digital paragraph for the mixed-document Phase 3 fixture. " * 10
    for line_index, start in enumerate(range(0, len(paragraph), 90)):
        digital.insert_text((72, 72 + line_index * 14), paragraph[start : start + 90], fontsize=11)

    scan = document.new_page(width=612, height=792)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 612, 792), 0)
    pix.clear_with(255)
    scan.insert_image(scan.rect, pixmap=pix)

    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    output_dir = tmp_path / "output"
    db_path = tmp_path / "data" / "jobs.db"
    monkeypatch.setenv("EXTRACTION_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("EXTRACTION_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("EXTRACTION_MAX_FILE_BYTES", "10485760")
    monkeypatch.setenv("EXTRACTION_BENCHMARK_ENABLED", "true")
    monkeypatch.setenv("DOCLING_WARM_ON_STARTUP", "false")
    monkeypatch.setenv("EURI_API_KEY", "")
    get_settings.cache_clear()
    get_job_store.cache_clear()
    get_docling_adapter.cache_clear()
    get_gemini_adapter.cache_clear()
    get_groq_adapter.cache_clear()
    settings = get_settings()
    yield settings
    get_settings.cache_clear()
    get_job_store.cache_clear()
    get_docling_adapter.cache_clear()
    get_gemini_adapter.cache_clear()
    get_groq_adapter.cache_clear()


@pytest.fixture
def fake_docling_adapter(tmp_settings: Settings) -> DoclingAdapter:
    factory = converter_factory_for(
        {
            "digital-layout": layout_items(),
            "digital-table": table_items(),
            "formula-code": [
                FakeItem("formula", "E = mc^2", 1, FakeBBox(80, 200, 200, 240)),
                FakeItem("code", "print('ok')", 1, FakeBBox(80, 260, 300, 320)),
            ],
            "private-ocr": ocr_items(),
        }
    )
    return DoclingAdapter(tmp_settings, converter_factory=factory)


@pytest.fixture
async def client(tmp_settings: Settings, fake_docling_adapter: DoclingAdapter):
    app = create_app()
    app.dependency_overrides[get_docling_adapter] = lambda: fake_docling_adapter
    job_store = get_job_store()
    await job_store.initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()
    get_job_store.cache_clear()
    get_docling_adapter.cache_clear()
    get_gemini_adapter.cache_clear()
    get_groq_adapter.cache_clear()


async def wait_for_terminal_status(client: AsyncClient, job_id: str, *, attempts: int = 40) -> dict:
    for _ in range(attempts):
        response = await client.get(f"/api/v1/extractions/{job_id}")
        payload = response.json()
        if payload["status"] in {"completed", "completed_with_warnings", "failed"}:
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not reach a terminal status.")


def _workspace_pdf(tmp_path: Path, pdf_bytes: bytes) -> Path:
    workspace = tmp_path / "doc-workspace"
    (workspace / "raw").mkdir(parents=True)
    (workspace / "assets" / "pictures").mkdir(parents=True)
    pdf_path = workspace / "source.pdf"
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


@pytest.mark.asyncio
async def test_docling_profiles_are_warmed_and_reused(fake_docling_adapter: DoclingAdapter) -> None:
    warmed = fake_docling_adapter.warm_profiles()
    assert warmed == [
        "digital-layout",
        "digital-table",
        "formula-code",
        "private-ocr",
    ]
    first = fake_docling_adapter.get_converter("digital-table")
    second = fake_docling_adapter.get_converter("digital-table")
    assert first is second
    assert fake_docling_adapter.get_converter("private-ocr") is not first


@pytest.mark.asyncio
async def test_docling_adapter_maps_selected_pages_back_to_originals(
    tmp_path: Path,
    fake_docling_adapter: DoclingAdapter,
) -> None:
    pdf_path = _workspace_pdf(tmp_path, make_digital_pdf_bytes("page-one", "page-two"))
    result = await fake_docling_adapter.extract(
        pdf_path,
        [2],
        tasks=[
            ExtractionTask(
                document_id="doc-workspace",
                page=2,
                kind="layout",
                extractor="docling",
                profile="digital-layout",
            )
        ],
    )

    assert result.metadata["temporary_pages"] == [1]
    assert result.metadata["original_pages"] == [2]
    assert result.pages[0].page == 2
    assert result.pages[0].primary_route == "docling"
    assert result.pages[0].elements[0].extractor.profile == "digital-layout"
    assert result.pages[0].elements[0].bbox is not None
    assert not any(pdf_path.parent.joinpath("raw").glob("docling-*.pdf"))


@pytest.mark.asyncio
async def test_docling_table_profile_emits_structured_table(
    tmp_path: Path,
    fake_docling_adapter: DoclingAdapter,
) -> None:
    pdf_path = _workspace_pdf(tmp_path, make_digital_pdf_bytes("table page"))
    result = await fake_docling_adapter.extract(
        pdf_path,
        [1],
        tasks=[
            ExtractionTask(
                document_id="doc-workspace",
                page=1,
                kind="table_structure",
                extractor="docling",
                profile="digital-table",
            )
        ],
    )
    table = next(element for element in result.pages[0].elements if element.type == ElementType.TABLE)
    assert table.markdown and "Region" in table.markdown
    assert table.html and "<table>" in table.html


@pytest.mark.asyncio
async def test_formula_code_profile_emits_formula_and_code(
    tmp_path: Path,
    fake_docling_adapter: DoclingAdapter,
) -> None:
    pdf_path = _workspace_pdf(tmp_path, make_digital_pdf_bytes("formula page"))
    result = await fake_docling_adapter.extract(
        pdf_path,
        [1],
        tasks=[
            ExtractionTask(
                document_id="doc-workspace",
                page=1,
                kind="formula_code",
                extractor="docling",
                profile="formula-code",
            )
        ],
    )
    types = {element.type for element in result.pages[0].elements}
    assert ElementType.FORMULA in types
    assert ElementType.CODE in types


@pytest.mark.asyncio
async def test_private_ocr_profile_returns_local_text(
    tmp_path: Path,
    fake_docling_adapter: DoclingAdapter,
) -> None:
    pdf_path = _workspace_pdf(tmp_path, make_scanned_like_pdf_bytes())
    result = await fake_docling_adapter.extract(
        pdf_path,
        [1],
        tasks=[
            ExtractionTask(
                document_id="doc-workspace",
                page=1,
                kind="ocr",
                extractor="docling",
                profile="private-ocr",
            )
        ],
    )
    assert "Local OCR recovered this scan text." in (result.pages[0].elements[0].text or "")
    assert result.attempts[0].profile == "private-ocr"


@pytest.mark.asyncio
async def test_force_docling_layout_via_api(client: AsyncClient) -> None:
    upload = await client.post(
        "/api/v1/extractions",
        files={"file": ("digital.pdf", make_digital_pdf_bytes(), "application/pdf")},
        data={"force_extractor": "docling:digital-layout"},
    )
    assert upload.status_code == 202
    job = await wait_for_terminal_status(client, upload.json()["job_id"])
    assert job["status"] == "completed"

    document = (await client.get(f"/api/v1/extractions/{job['job_id']}/document")).json()
    page = document["pages"][0]
    assert page["primary_route"] == "docling"
    assert page["elements"][0]["extractor"]["profile"] == "digital-layout"
    assert any(element["type"] == "heading" for element in page["elements"])

    report = (await client.get(f"/api/v1/extractions/{job['job_id']}/report")).json()
    assert report["phase"] == "3-docling-baseline"
    assert "docling" in report["extractors"]
    assert "digital-layout" in report["profiles"]


@pytest.mark.asyncio
async def test_local_only_scan_uses_private_ocr(client: AsyncClient) -> None:
    upload = await client.post(
        "/api/v1/extractions",
        files={"file": ("scan-like.pdf", make_scanned_like_pdf_bytes(), "application/pdf")},
        data={"allow_managed_apis": "false"},
    )
    assert upload.status_code == 202
    job = await wait_for_terminal_status(client, upload.json()["job_id"])
    assert job["status"] == "completed"

    document = (await client.get(f"/api/v1/extractions/{job['job_id']}/document")).json()
    page = document["pages"][0]
    assert page["primary_route"] == "docling"
    assert page["elements"][0]["text"] == "Local OCR recovered this scan text."
    assert document["summary"]["scanned_pages"] == [1]
    assert document["summary"]["failed_pages"] == []


@pytest.mark.asyncio
async def test_mixed_document_uses_pymupdf_and_local_ocr(
    tmp_path: Path,
    tmp_settings: Settings,
    fake_docling_adapter: DoclingAdapter,
) -> None:
    pdf_path = tmp_path / "mixed.pdf"
    pdf_path.write_bytes(make_mixed_pdf_bytes())
    inspector = PdfInspector(tmp_settings)
    inspection = inspector.inspect(pdf_path, document_id="mixed")
    assert inspection.pages[0].probable_scan is False
    assert inspection.pages[1].probable_scan is True

    service = ExtractionService(
        job_service=JobService(JobStore(tmp_settings)),
        settings=tmp_settings,
        inspector=inspector,
        pymupdf_adapter=PyMuPDFAdapter(tmp_settings),
        docling_adapter=fake_docling_adapter,
        workspace_manager=WorkspaceManager(tmp_settings),
    )
    pages = await service._extract_pages(
        pdf_path=pdf_path,
        inspection=inspection,
        force_extractor=None,
        allow_managed_apis=False,
    )
    assert pages.pages[0].primary_route == "pymupdf"
    assert pages.pages[1].primary_route == "docling"
    assert pages.pages[1].attempts[0].profile == "private-ocr"
    assert pages.pages[1].elements
