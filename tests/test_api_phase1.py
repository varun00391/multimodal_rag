import asyncio
import io
from pathlib import Path

import fitz
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    output_dir = tmp_path / "output"
    db_path = tmp_path / "data" / "jobs.db"
    monkeypatch.setenv("EXTRACTION_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("EXTRACTION_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("EXTRACTION_MAX_FILE_BYTES", "1048576")
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


def make_pdf_bytes(text: str = "Hello extraction phase one.") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


async def _wait_for_terminal_status(client: AsyncClient, job_id: str) -> dict:
    for _ in range(20):
        response = await client.get(f"/api/v1/extractions/{job_id}")
        payload = response.json()
        if payload["status"] in {"completed", "completed_with_warnings", "failed"}:
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish.")


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_upload_valid_pdf_returns_202(client: AsyncClient, tmp_settings: Settings) -> None:
    pdf_bytes = make_pdf_bytes()
    response = await client.post(
        "/api/v1/extractions",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        data={"allow_managed_apis": "true", "visual_understanding": "false"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"].startswith("job-")
    assert payload["status"] == "queued"

    job = await _wait_for_terminal_status(client, payload["job_id"])
    assert job["status"] in {"completed", "completed_with_warnings"}
    assert job["page_count"] == 1
    assert len(job["sha256"]) == 64
    workspace = Path(tmp_settings.extraction_output_dir) / job["document_id"]
    assert (workspace / "source.pdf").exists()


@pytest.mark.asyncio
async def test_upload_rejects_invalid_pdf(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/extractions",
        files={"file": ("bad.pdf", b"not-a-pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PDF_SIGNATURE"


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/extractions",
        files={"file": ("large.pdf", b"%PDF-" + (b"0" * 2_000_000), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_upload_rejects_force_extractor_when_benchmark_disabled(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/extractions",
        files={"file": ("sample.pdf", make_pdf_bytes(), "application/pdf")},
        data={"force_extractor": "docling:digital-layout"},
    )
    assert response.status_code == 403
    payload = response.json()["error"]
    assert payload["code"] == "BENCHMARK_NOT_ENABLED"
    assert payload["details"]["force_extractor"] == "docling:digital-layout"


@pytest.mark.asyncio
async def test_upload_rejects_compare_extractors_when_benchmark_disabled(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/extractions",
        files={"file": ("sample.pdf", make_pdf_bytes(), "application/pdf")},
        data={"compare_extractors": "true"},
    )
    assert response.status_code == 403
    payload = response.json()["error"]
    assert payload["code"] == "BENCHMARK_NOT_ENABLED"
    assert payload["details"]["compare_extractors"] is True


@pytest.mark.asyncio
async def test_upload_treats_swagger_sentinel_force_extractor_as_unset(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/extractions",
        files={"file": ("sample.pdf", make_pdf_bytes(), "application/pdf")},
        data={
            "allow_managed_apis": "true",
            "visual_understanding": "false",
            "force_extractor": "null",
            "compare_extractors": "false",
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_openapi_hides_benchmark_form_fields(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()["components"]["schemas"][
        "Body_create_extraction_api_v1_extractions_post"
    ]
    assert "force_extractor" not in schema["properties"]
    assert "compare_extractors" not in schema["properties"]
    assert "file" in schema["properties"]
