from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import fitz
import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.euri_client import GeminiCompletion
from app.adapters.gemini_adapter import GeminiAdapter, estimate_cost_usd
from app.adapters.gemini_pages import bbox_to_pdf_points, consecutive_groups
from app.adapters.gemini_schema import GeminiBBox, parse_gemini_payload
from app.adapters.pymupdf_adapter import PyMuPDFAdapter
from app.api.dependencies import get_docling_adapter, get_gemini_adapter, get_groq_adapter, get_job_store
from app.config import Settings, get_settings
from app.inspection.pdf_inspector import PdfInspector
from app.main import create_app
from app.models.canonical import ElementType
from app.models.routing import ExtractionTask
from app.services.extraction_service import ExtractionService
from app.services.job_service import JobService
from app.storage.jobs import JobStore
from app.storage.workspace import WorkspaceManager


class FakeCompleter:
    def __init__(self, payloads: str | list[str]) -> None:
        self.payloads = [payloads] if isinstance(payloads, str) else list(payloads)
        self.calls: list[dict] = []

    async def complete(self, *, model: str, messages: list[dict], timeout_seconds: int) -> GeminiCompletion:
        self.calls.append(
            {"model": model, "messages": messages, "timeout_seconds": timeout_seconds}
        )
        index = min(len(self.calls) - 1, len(self.payloads) - 1)
        return GeminiCompletion(
            content=self.payloads[index],
            model=model,
            finish_reason="stop",
            prompt_tokens=11,
            completion_tokens=22,
            total_tokens=33,
        )


def make_scanned_like_pdf_bytes(page_count: int = 1) -> bytes:
    document = fitz.open()
    for _ in range(page_count):
        page = document.new_page(width=612, height=792)
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 612, 792), 0)
        pix.clear_with(255)
        page.insert_image(page.rect, pixmap=pix)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def gemini_payload(page: int = 1, text: str = "Recovered scan text") -> str:
    return json.dumps(
        {
            "pages": [
                {
                    "page": page,
                    "elements": [
                        {
                            "type": "paragraph",
                            "text": text,
                            "reading_order": 1,
                            "bbox": {"left": 0.1, "top": 0.1, "right": 0.9, "bottom": 0.2},
                            "confidence": 0.91,
                            "uncertain": False,
                        }
                    ],
                }
            ]
        }
    )


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    output_dir = tmp_path / "output"
    db_path = tmp_path / "data" / "jobs.db"
    monkeypatch.setenv("EXTRACTION_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("EXTRACTION_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("EXTRACTION_MAX_FILE_BYTES", "10485760")
    monkeypatch.setenv("EXTRACTION_BENCHMARK_ENABLED", "true")
    monkeypatch.setenv("DOCLING_WARM_ON_STARTUP", "false")
    monkeypatch.setenv("EURI_API_KEY", "test-euri-key")
    monkeypatch.setenv("EURI_BASE_URL", "https://api.euron.one/api/v1/euri")
    monkeypatch.setenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_RETRY_BACKOFF_SECONDS", "0")
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


def _workspace_pdf(tmp_path: Path, pdf_bytes: bytes) -> Path:
    workspace = tmp_path / "doc-workspace"
    (workspace / "raw").mkdir(parents=True)
    (workspace / "assets" / "pictures").mkdir(parents=True)
    pdf_path = workspace / "source.pdf"
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def test_consecutive_groups_split_runs_and_target_size() -> None:
    assert consecutive_groups([1, 2, 3, 4, 5, 6, 10, 11], target=5, max_size=10) == [
        [1, 2, 3, 4, 5],
        [6],
        [10, 11],
    ]


def test_normalized_bbox_converts_to_pdf_points() -> None:
    bbox = bbox_to_pdf_points(GeminiBBox(left=0.1, top=0.2, right=0.5, bottom=0.4), 612, 792)
    assert bbox.left == pytest.approx(61.2)
    assert bbox.top == pytest.approx(158.4)
    assert bbox.right == pytest.approx(306.0)
    assert bbox.bottom == pytest.approx(316.8)


def test_thousand_scale_bbox_converts_to_pdf_points() -> None:
    bbox = bbox_to_pdf_points(GeminiBBox(left=100, top=200, right=500, bottom=400), 612, 792)
    assert bbox.left == pytest.approx(61.2)
    assert bbox.top == pytest.approx(158.4)


def test_malformed_gemini_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        parse_gemini_payload("this is not json")


def test_cost_is_estimated_from_token_usage() -> None:
    assert estimate_cost_usd(
        1_000_000,
        1_000_000,
        input_usd_per_million=0.15,
        output_usd_per_million=0.60,
    ) == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_gemini_adapter_maps_euron_json_to_canonical(
    tmp_path: Path,
    tmp_settings: Settings,
) -> None:
    pdf_path = _workspace_pdf(tmp_path, make_scanned_like_pdf_bytes())
    completer = FakeCompleter(gemini_payload())
    adapter = GeminiAdapter(tmp_settings, completer=completer)
    result = await adapter.extract(
        pdf_path,
        [1],
        tasks=[ExtractionTask(document_id="doc-workspace", page=1, kind="ocr", extractor="gemini")],
    )

    assert adapter.is_configured
    assert result.pages[0].primary_route == "gemini"
    element = result.pages[0].elements[0]
    assert element.type == ElementType.PARAGRAPH
    assert element.text == "Recovered scan text"
    assert element.extractor is not None
    assert element.extractor.model == "gemini-2.5-flash"
    assert element.metadata["provider"] == "euron"
    assert element.bbox is not None
    assert element.bbox.left == pytest.approx(61.2)
    assert completer.calls[0]["model"] == "gemini-2.5-flash"
    assert result.metadata["provider"] == "euron"
    assert result.metadata["usage"]["prompt_tokens"] == 11
    assert result.metadata["usage"]["estimated_cost_usd"] > 0
    assert (pdf_path.parent / "assets" / "pages" / "page_1.png").exists()
    assert (pdf_path.parent / "raw" / "gemini-pages-1.json").exists()


@pytest.mark.asyncio
async def test_gemini_adapter_rejects_malformed_response(
    tmp_path: Path,
    tmp_settings: Settings,
) -> None:
    pdf_path = _workspace_pdf(tmp_path, make_scanned_like_pdf_bytes())
    adapter = GeminiAdapter(tmp_settings, completer=FakeCompleter("not-json"))
    result = await adapter.extract(pdf_path, [1], tasks=[])
    assert result.pages[0].errors[0].code == "GEMINI_RESPONSE_INVALID"
    assert result.attempts[0].status == "failed"


@pytest.mark.asyncio
async def test_managed_apis_off_never_calls_euron(
    tmp_path: Path,
    tmp_settings: Settings,
) -> None:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(make_scanned_like_pdf_bytes())
    completer = FakeCompleter(gemini_payload())
    inspector = PdfInspector(tmp_settings)
    inspection = inspector.inspect(pdf_path, document_id="scan")
    service = ExtractionService(
        job_service=JobService(JobStore(tmp_settings)),
        settings=tmp_settings,
        inspector=inspector,
        pymupdf_adapter=PyMuPDFAdapter(tmp_settings),
        docling_adapter=object(),  # unused when scans are blocked from managed APIs
        workspace_manager=WorkspaceManager(tmp_settings),
        gemini_adapter=GeminiAdapter(tmp_settings, completer=completer),
    )
    outcome = await service._extract_pages(
        pdf_path=pdf_path,
        inspection=inspection,
        force_extractor="gemini",
        allow_managed_apis=False,
    )
    assert completer.calls == []
    assert outcome.pages[0].errors[0].code == "MANAGED_APIS_PROHIBITED"


@pytest.mark.asyncio
async def test_scan_uses_euron_gemini_when_managed_apis_allowed(
    tmp_path: Path,
    tmp_settings: Settings,
) -> None:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(make_scanned_like_pdf_bytes())
    completer = FakeCompleter(gemini_payload(text="Invoice total 120.50 USD"))
    inspector = PdfInspector(tmp_settings)
    inspection = inspector.inspect(pdf_path, document_id="scan")
    assert inspection.pages[0].probable_scan is True

    service = ExtractionService(
        job_service=JobService(JobStore(tmp_settings)),
        settings=tmp_settings,
        inspector=inspector,
        pymupdf_adapter=PyMuPDFAdapter(tmp_settings),
        docling_adapter=object(),
        workspace_manager=WorkspaceManager(tmp_settings),
        gemini_adapter=GeminiAdapter(tmp_settings, completer=completer),
    )
    outcome = await service._extract_pages(
        pdf_path=pdf_path,
        inspection=inspection,
        force_extractor=None,
        allow_managed_apis=True,
    )
    assert completer.calls
    assert outcome.pages[0].primary_route == "gemini"
    assert outcome.pages[0].elements[0].text == "Invoice total 120.50 USD"
    assert outcome.estimated_cost_usd > 0
    assert outcome.prompt_tokens == 11


@pytest.mark.asyncio
async def test_force_gemini_via_api(tmp_settings: Settings) -> None:
    completer = FakeCompleter(gemini_payload(text="Forced Gemini page"))
    adapter = GeminiAdapter(tmp_settings, completer=completer)
    app = create_app()
    app.dependency_overrides[get_gemini_adapter] = lambda: adapter
    job_store = get_job_store()
    await job_store.initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/api/v1/extractions",
            files={"file": ("scan-like.pdf", make_scanned_like_pdf_bytes(), "application/pdf")},
            data={"force_extractor": "gemini"},
        )
        assert upload.status_code == 202
        job_id = upload.json()["job_id"]
        for _ in range(40):
            payload = (await client.get(f"/api/v1/extractions/{job_id}")).json()
            if payload["status"] in {"completed", "completed_with_warnings", "failed"}:
                break
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("Job did not finish.")

        document = (await client.get(f"/api/v1/extractions/{job_id}/document")).json()
        report = (await client.get(f"/api/v1/extractions/{job_id}/report")).json()
    app.dependency_overrides.clear()
    get_job_store.cache_clear()
    get_gemini_adapter.cache_clear()
    get_groq_adapter.cache_clear()

    assert document["pages"][0]["primary_route"] == "gemini"
    assert document["pages"][0]["elements"][0]["text"] == "Forced Gemini page"
    assert report["phase"] == "4-gemini-baseline"
    assert report["gemini_provider"] == "euron"
    assert report["usage"]["prompt_tokens"] == 11
    assert report["usage"]["estimated_cost_usd"] > 0
    assert completer.calls
    assert document["summary"]["estimated_cost_usd"] > 0
