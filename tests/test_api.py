from __future__ import annotations

import time

from fastapi.testclient import TestClient

from extraction.app import app
from extraction.settings import get_settings


def test_health(settings) -> None:
    del settings
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_csv_upload_job(settings) -> None:
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/extractions",
            files={"file": ("people.csv", b"name,role\nAda,Engineer\n", "text/csv")},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        document = None
        for _ in range(50):
            status = client.get(f"/api/v1/extractions/{job_id}")
            assert status.status_code == 200
            if status.json()["status"] == "completed":
                document = client.get(f"/api/v1/extractions/{job_id}/document")
                break
            if status.json()["status"] == "failed":
                raise AssertionError(status.json())
            time.sleep(0.1)
        assert document is not None
        assert document.status_code == 200
        payload = document.json()
        assert payload["units"][0]["elements"][0]["table"]["rows"][0][0] == "Ada"


def test_missing_job(settings) -> None:
    del settings
    with TestClient(app) as client:
        response = client.get("/api/v1/extractions/does-not-exist")
    assert response.status_code == 404
