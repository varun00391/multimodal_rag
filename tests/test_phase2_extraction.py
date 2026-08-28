import asyncio
import io
from pathlib import Path

import fitz
import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.pymupdf_adapter import PyMuPDFAdapter
from app.config import Settings, get_settings
from app.inspection.pdf_inspector import PdfInspector
from app.main import create_app


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    output_dir = tmp_path / "output"
    db_path = tmp_path / "data" / "jobs.db"
    monkeypatch.setenv("EXTRACTION_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("EXTRACTION_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("EXTRACTION_MAX_FILE_BYTES", "10485760")
    monkeypatch.setenv("EXTRACTION_BENCHMARK_ENABLED", "false")
    monkeypatch.setenv("EURI_API_KEY", "")
    get_settings.cache_clear()
    settings = get_settings()
    yield settings
    get_settings.cache_clear()
    from app.api.dependencies import (
        get_docling_adapter,
        get_gemini_adapter,
        get_groq_adapter,
        get_job_store,
    )

    get_job_store.cache_clear()
    get_docling_adapter.cache_clear()
    get_gemini_adapter.cache_clear()
    get_groq_adapter.cache_clear()


@pytest.fixture
async def client(tmp_settings: Settings):
    from app.api.dependencies import get_job_store

    get_job_store.cache_clear()
    app = create_app()
    job_store = get_job_store()
    await job_store.initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    get_job_store.cache_clear()


def make_digital_pdf_bytes(text: str = "Hello extraction phase two.") -> bytes:
    document = fitz.open()
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


async def wait_for_terminal_status(client: AsyncClient, job_id: str, *, attempts: int = 20) -> dict:
    for _ in range(attempts):
        response = await client.get(f"/api/v1/extractions/{job_id}")
        payload = response.json()
        if payload["status"] in {"completed", "completed_with_warnings", "failed"}:
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not reach a terminal status.")


@pytest.mark.asyncio
async def test_phase2_digital_pdf_produces_document_json(
    client: AsyncClient,
    tmp_settings: Settings,
) -> None:
    pdf_bytes = make_digital_pdf_bytes()
    upload = await client.post(
        "/api/v1/extractions",
        files={"file": ("digital.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 202
    job_id = upload.json()["job_id"]

    job = await wait_for_terminal_status(client, job_id)
    assert job["status"] == "completed"

    document_response = await client.get(f"/api/v1/extractions/{job_id}/document")
    assert document_response.status_code == 200
    document = document_response.json()
    assert document["page_count"] == 1
    assert document["pages"][0]["primary_route"] == "pymupdf"
    assert document["pages"][0]["elements"]
    first_element = document["pages"][0]["elements"][0]
    assert first_element["bbox"]["coordinate_origin"] == "top-left"
    assert first_element["text"]

    workspace = Path(tmp_settings.extraction_output_dir) / job["document_id"]
    assert (workspace / "inspection.json").exists()
    assert (workspace / "document.json").exists()
    assert (workspace / "extraction-report.json").exists()


@pytest.mark.asyncio
async def test_phase2_scanned_pdf_is_identified_not_fully_extracted(
    client: AsyncClient,
    tmp_settings: Settings,
) -> None:
    pdf_bytes = make_scanned_like_pdf_bytes()
    upload = await client.post(
        "/api/v1/extractions",
        files={"file": ("scan-like.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 202
    job_id = upload.json()["job_id"]

    job = await wait_for_terminal_status(client, job_id)
    assert job["status"] == "completed_with_warnings"

    document = (await client.get(f"/api/v1/extractions/{job_id}/document")).json()
    page = document["pages"][0]
    assert page["primary_route"] is None
    assert page["warnings"]
    assert page["errors"][0]["code"] == "SCANNED_PAGE_NOT_EXTRACTED"
    assert document["summary"]["scanned_pages"] == [1]

    inspection = (await client.get(f"/api/v1/extractions/{job_id}/report")).json()
    assert inspection["inspection_summary"]["scanned_pages"] == [1]


@pytest.mark.asyncio
async def test_pymupdf_adapter_extracts_coordinates(tmp_path: Path, tmp_settings: Settings) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(make_digital_pdf_bytes("Coordinate test text"))
    workspace_id = "test-doc"
    workspace = tmp_path / workspace_id
    workspace.mkdir()
    target_pdf = workspace / "source.pdf"
    target_pdf.write_bytes(pdf_path.read_bytes())

    adapter = PyMuPDFAdapter(tmp_settings)
    result = await adapter.extract(target_pdf, [1], tasks=[])
    assert result.pages[0].elements
    bbox = result.pages[0].elements[0].bbox
    assert bbox is not None
    assert bbox.left >= 0
    assert bbox.top >= 0
    assert bbox.right > bbox.left
    assert bbox.bottom > bbox.top


@pytest.mark.asyncio
async def test_inspector_flags_probable_scan(tmp_path: Path, tmp_settings: Settings) -> None:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(make_scanned_like_pdf_bytes())
    inspector = PdfInspector(tmp_settings)
    inspection = inspector.inspect(pdf_path, document_id="scan-doc")
    assert inspection.pages[0].probable_scan is True
