from __future__ import annotations

import asyncio
import io
from pathlib import Path

import fitz
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.execution.executor import ExtractionExecutor
from app.execution.limits import JobLimiter, ProviderCircuitBreaker
from app.main import create_app
from app.models.canonical import (
    CanonicalElement,
    CanonicalExtractionResult,
    CanonicalPage,
    ElementType,
    ExtractionAttempt,
)
from app.models.inspection import DocumentInspection, PageInspection, TextSignals
from app.models.jobs import ExtractionPolicy
from app.models.routing import ExtractionGroup, ExtractionTask
from app.observability.metrics import get_metrics
from app.storage.cache import ExtractionCache, version_fingerprint


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    output_dir = tmp_path / "output"
    db_path = tmp_path / "data" / "jobs.db"
    monkeypatch.setenv("EXTRACTION_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("EXTRACTION_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("EXTRACTION_CACHE_ENABLED", "true")
    monkeypatch.setenv("EXTRACTION_BENCHMARK_ENABLED", "false")
    monkeypatch.setenv("EXTRACTION_MAX_INFLIGHT_JOBS", "64")
    monkeypatch.setenv("DOCLING_WARM_ON_STARTUP", "false")
    monkeypatch.setenv("GROQ_VISUAL_EXTRACTION_ENABLED", "false")
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
    await get_job_store().initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    get_job_store.cache_clear()


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values = {
        "extraction_output_dir": tmp_path / "output",
        "extraction_database_path": tmp_path / "data" / "jobs.db",
        "extraction_cache_enabled": True,
        "extraction_circuit_failure_threshold": 1,
        "extraction_circuit_recovery_seconds": 60.0,
        "extraction_max_inflight_jobs": 2,
        "extraction_max_concurrent_jobs": 2,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_pdf_bytes(text: str = "Hello extraction phase nine.") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


async def _wait_for_terminal_status(client: AsyncClient, job_id: str) -> dict:
    for _ in range(40):
        response = await client.get(f"/api/v1/extractions/{job_id}")
        payload = response.json()
        if payload["status"] in {"completed", "completed_with_warnings", "failed"}:
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish.")


def _canonical_page(extractor: str, text: str, page: int = 1) -> CanonicalPage:
    return CanonicalPage(
        page=page,
        width=612,
        height=792,
        primary_route=extractor,
        extraction_routes=[extractor],
        elements=[
            CanonicalElement(
                element_id=f"{extractor}-1",
                type=ElementType.PARAGRAPH,
                page=page,
                reading_order=1,
                text=text,
            )
        ],
        attempts=[ExtractionAttempt(attempt=1, extractor=extractor, status="completed", element_count=1)],
    )


class RecordingAdapter:
    def __init__(self, name: str, page: CanonicalPage | None = None, *, fail: bool = False) -> None:
        self.name = name
        self.calls: list[dict] = []
        self._page = page
        self._fail = fail

    async def extract(self, pdf_path, pages, tasks, context_pages=None):
        self.calls.append({"pages": list(pages), "context_pages": list(context_pages or [])})
        if self._fail:
            raise RuntimeError(f"{self.name} failed")
        page = self._page or _canonical_page(self.name, "ok", page=pages[0])
        return CanonicalExtractionResult(pages=[page], attempts=page.attempts)


def _group(extractor: str, page: int = 1, document_id: str = "abc") -> ExtractionGroup:
    return ExtractionGroup(
        group_id=f"{extractor}-native-{page:04d}",
        document_id=document_id,
        extractor=extractor,
        kind="native_text",
        pages=[page],
        tasks=[ExtractionTask(page=page, kind="native_text", extractor=extractor)],
    )


def test_version_fingerprint_changes_with_schema(tmp_path: Path) -> None:
    first = _settings(tmp_path, extraction_schema_version="1.0")
    second = _settings(tmp_path, extraction_schema_version="2.0")
    assert version_fingerprint(first) != version_fingerprint(second)


def test_cache_rejects_incompatible_schema(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    cache = ExtractionCache(settings)
    policy = ExtractionPolicy()
    key = cache.document_key(sha256="abc", policy=policy)
    cache.put_document(
        key,
        document={"status": "completed", "pages": []},
        report={"job_id": "job-1"},
        inspection={"document_id": "abc", "page_count": 1, "schema_version": "1.0", "pages": []},
        routing={"plans": [], "groups": []},
        status="completed",
    )
    assert cache.get_document(key) is not None

    other = ExtractionCache(_settings(tmp_path, extraction_schema_version="9.9"))
    assert other.document_key(sha256="abc", policy=policy) != key
    assert other.get_document(key) is None


@pytest.mark.asyncio
async def test_group_cache_skips_adapter_on_second_run(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    adapter = RecordingAdapter("pymupdf", _canonical_page("pymupdf", "cached text"))
    executor = ExtractionExecutor(
        settings,
        adapter,  # type: ignore[arg-type]
        RecordingAdapter("docling"),  # type: ignore[arg-type]
        cache=ExtractionCache(settings),
        circuit_breaker=ProviderCircuitBreaker(settings),
        metrics=get_metrics(),
    )
    groups = [_group("pymupdf")]
    first = await executor.run(pdf_path, groups)
    second = await executor.run(pdf_path, groups)
    assert len(adapter.calls) == 1
    assert first[0].cache_hit is False
    assert second[0].cache_hit is True
    assert second[0].result is not None
    assert second[0].result.pages[0].elements[0].text == "cached text"


@pytest.mark.asyncio
async def test_circuit_open_does_not_cancel_other_extractors(tmp_path: Path) -> None:
    settings = _settings(tmp_path, extraction_circuit_failure_threshold=1)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    pymupdf = RecordingAdapter("pymupdf", _canonical_page("pymupdf", "kept"))
    gemini = RecordingAdapter("gemini", fail=True)
    breaker = ProviderCircuitBreaker(settings)
    executor = ExtractionExecutor(
        settings,
        pymupdf,  # type: ignore[arg-type]
        RecordingAdapter("docling"),  # type: ignore[arg-type]
        gemini,  # type: ignore[arg-type]
        cache=ExtractionCache(settings),
        circuit_breaker=breaker,
        metrics=get_metrics(),
    )
    first = await executor.run(pdf_path, [_group("gemini", page=1)])
    second = await executor.run(
        pdf_path,
        [_group("gemini", page=2), _group("pymupdf", page=1)],
    )
    runs = first + second
    gemini_runs = [run for run in runs if run.group.extractor == "gemini"]
    pymupdf_runs = [run for run in runs if run.group.extractor == "pymupdf"]
    assert any(run.error is not None for run in gemini_runs)
    assert any(run.circuit_open for run in gemini_runs)
    assert pymupdf_runs[0].result is not None
    assert pymupdf.calls
    assert len(gemini.calls) == 1
    assert breaker.snapshot()["gemini"]["state"] == "open"


def test_job_limiter_rejects_when_full(tmp_path: Path) -> None:
    limiter = JobLimiter(_settings(tmp_path, extraction_max_inflight_jobs=1))
    assert limiter.try_accept() is True
    assert limiter.try_accept() is False
    limiter.release_accepted()
    assert limiter.try_accept() is True


@pytest.mark.asyncio
async def test_repeated_upload_uses_document_cache(client: AsyncClient) -> None:
    pdf_bytes = make_pdf_bytes()
    first = await client.post(
        "/api/v1/extractions",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert first.status_code == 202
    first_job = await _wait_for_terminal_status(client, first.json()["job_id"])
    assert first_job["status"] in {"completed", "completed_with_warnings"}
    assert first_job["cache_hit"] is False
    assert first_job["duration_ms"] is not None

    second = await client.post(
        "/api/v1/extractions",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert second.status_code == 202
    second_job = await _wait_for_terminal_status(client, second.json()["job_id"])
    assert second_job["status"] in {"completed", "completed_with_warnings"}
    assert second_job["cache_hit"] is True

    report = await client.get(f"/api/v1/extractions/{second_job['job_id']}/report")
    assert report.status_code == 200
    payload = report.json()
    assert payload["cache"]["hit"] is True
    assert payload["cache"]["document_hit"] is True
    assert payload["phase"] == "9-reporting-cache-hardening"
    assert "versions" in payload
    assert "circuit_breakers" in payload
    assert "durations" in payload or payload["duration_ms"] >= 0
    assert payload["pages"]


@pytest.mark.asyncio
async def test_report_includes_hardening_fields(client: AsyncClient) -> None:
    pdf_bytes = make_pdf_bytes("Phase nine report fields.")
    response = await client.post(
        "/api/v1/extractions",
        files={"file": ("report.pdf", pdf_bytes, "application/pdf")},
    )
    job = await _wait_for_terminal_status(client, response.json()["job_id"])
    report = (await client.get(f"/api/v1/extractions/{job['job_id']}/report")).json()
    assert report["phase"] == "9-reporting-cache-hardening"
    assert report["versions"]["schema_version"]
    assert report["cache"]["enabled"] is True
    assert "gemini" in report["circuit_breakers"]
    assert "inspect_ms" in report["durations"] or report["cache"]["hit"] is True
    metrics = (await client.get("/api/v1/metrics")).json()
    assert metrics["jobs_completed"] >= 1


@pytest.mark.asyncio
async def test_queue_backpressure_returns_429(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTION_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("EXTRACTION_DATABASE_PATH", str(tmp_path / "data" / "jobs.db"))
    monkeypatch.setenv("EXTRACTION_MAX_INFLIGHT_JOBS", "1")
    monkeypatch.setenv("DOCLING_WARM_ON_STARTUP", "false")
    monkeypatch.setenv("EURI_API_KEY", "")
    get_settings.cache_clear()
    from app.api.dependencies import get_job_store
    from app.execution.limits import get_job_limiter, reset_runtime_limits

    reset_runtime_limits()
    get_job_store.cache_clear()
    settings = get_settings()
    limiter = get_job_limiter(settings)
    assert limiter.try_accept() is True

    app = create_app()
    await get_job_store().initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/extractions",
            files={"file": ("busy.pdf", make_pdf_bytes(), "application/pdf")},
        )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "QUEUE_BACKPRESSURE"
    get_job_store.cache_clear()
    get_settings.cache_clear()
    reset_runtime_limits()


def test_inspection_models_round_trip_through_cache(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    cache = ExtractionCache(settings)
    inspection = DocumentInspection(
        schema_version="1.0",
        document_id="abc",
        page_count=1,
        pages=[
            PageInspection(
                page=1,
                width=612,
                height=792,
                text=TextSignals(character_count=12, printable_ratio=1.0),
            )
        ],
    )
    key = cache.inspection_key(sha256="abc", page_start=1, page_end=1)
    cache.put_inspection(key, inspection)
    loaded = cache.get_inspection(key)
    assert loaded is not None
    assert loaded.pages[0].text.character_count == 12
