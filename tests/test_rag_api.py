from __future__ import annotations

import hashlib
import time

from fastapi.testclient import TestClient

from extraction.app import app
from extraction.rag.embeddings import l2_normalize
from extraction.rag.store import MemoryChunkStore
from extraction.settings import get_settings


def _vector(text: str, dims: int = 768) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    seed = digest
    while len(values) < dims:
        values.extend((byte / 127.5) - 1.0 for byte in seed)
        seed = hashlib.sha256(seed).digest()
    return l2_normalize(values[:dims])


def test_index_and_ask_csv(settings, monkeypatch) -> None:
    MemoryChunkStore.reset()
    monkeypatch.setenv("QDRANT_URL", "memory://tests")
    monkeypatch.setenv("EURI_API_KEY", "test-euri")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    get_settings.cache_clear()

    def fake_embed_texts(settings, texts):
        del settings
        return [_vector(text) for text in texts]

    def fake_embed_children(settings, children, assets_dir):
        del assets_dir
        return fake_embed_texts(settings, [child.embed_text for child in children])

    def fake_answer(settings, question, parents):
        del settings, question
        return f"Ada is an Engineer. Source: {parents[0].filename}"

    monkeypatch.setattr("extraction.rag.service.embed_texts", fake_embed_texts)
    monkeypatch.setattr("extraction.rag.service.embed_children", fake_embed_children)
    monkeypatch.setattr("extraction.rag.service.answer_question", fake_answer)

    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/extractions",
            files={"file": ("people.csv", b"name,role\nAda,Engineer\n", "text/csv")},
        )
        assert upload.status_code == 200
        job_id = upload.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/api/v1/extractions/{job_id}")
            if status.json()["status"] == "completed":
                break
            if status.json()["status"] == "failed":
                raise AssertionError(status.json())
            time.sleep(0.1)
        else:
            raise AssertionError("extraction did not complete")

        indexed = client.post("/api/v1/index", json={"job_id": job_id})
        assert indexed.status_code == 200, indexed.text
        body = indexed.json()
        assert body["status"] == "indexed"
        assert body["child_count"] >= 1
        assert body["parent_count"] >= 1

        asked = client.post("/api/v1/ask", json={"question": "What is Ada's role?", "job_id": job_id})
        assert asked.status_code == 200, asked.text
        payload = asked.json()
        assert "Ada" in payload["answer"]
        assert payload["sources"]
        assert payload["sources"][0]["filename"] == "people.csv"

    MemoryChunkStore.reset()
    get_settings.cache_clear()


def test_index_missing_job(settings, monkeypatch) -> None:
    monkeypatch.setenv("QDRANT_URL", "memory://tests")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post("/api/v1/index", json={"job_id": "missing"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "JOB_NOT_FOUND"
    get_settings.cache_clear()


def test_embed_texts_maps_unauthorized_key(settings, monkeypatch) -> None:
    import httpx
    from openai import AuthenticationError

    from extraction.errors import ExtractionError
    from extraction.rag.embeddings import embed_texts

    error = AuthenticationError(
        "invalid",
        response=httpx.Response(401, request=httpx.Request("POST", "https://api.euron.one/api/v1/euri/embeddings")),
        body={"error": {"message": "Invalid or inactive API key"}},
    )

    class _FakeEmbeddings:
        def create(self, **kwargs):
            del kwargs
            raise error

    class _FakeClient:
        embeddings = _FakeEmbeddings()

    monkeypatch.setattr("extraction.rag.embeddings.get_euron_client", lambda _settings: _FakeClient())
    try:
        embed_texts(settings, ["hello"])
        raised = False
    except ExtractionError as exc:
        raised = exc.code == "EMBEDDINGS_UNAUTHORIZED"
    assert raised
