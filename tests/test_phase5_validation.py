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
    monkeypatch.setenv("EXTRACTION_MAX_FILE_BYTES", "10485760")
    monkeypatch.setenv("EXTRACTION_BENCHMARK_ENABLED", "false")
    monkeypatch.setenv("DOCLING_WARM_ON_STARTUP", "false")
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


def make_digital_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Hello extraction phase five.", fontsize=12)
    page.insert_text((72, 120), "Section Title", fontsize=18)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


async def wait_for_terminal_status(client: AsyncClient, job_id: str, *, attempts: int = 40) -> dict:
    for _ in range(attempts):
        response = await client.get(f"/api/v1/extractions/{job_id}")
        payload = response.json()
        if payload["status"] in {"completed", "completed_with_warnings", "failed"}:
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not reach a terminal status.")


@pytest.mark.asyncio
async def test_every_page_receives_validation_results(client: AsyncClient) -> None:
    upload = await client.post(
        "/api/v1/extractions",
        files={"file": ("digital.pdf", make_digital_pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 202
    job = await wait_for_terminal_status(client, upload.json()["job_id"])
    assert job["status"] in {"completed", "completed_with_warnings"}

    document = (await client.get(f"/api/v1/extractions/{job['job_id']}/document")).json()
    page = document["pages"][0]
    assert page["validation_confidence"] is not None
    assert page["overall_confidence"] is not None

    report = (await client.get(f"/api/v1/extractions/{job['job_id']}/report")).json()
    assert report["validation"]["page_count"] == 1
    assert report["validation"]["pages"][0]["page"] == 1
    assert "passed" in report["validation"]["pages"][0]
    assert isinstance(report["validation"]["pages"][0]["failures"], list)
