from fastapi.testclient import TestClient

import fitz

from app.core.config import get_settings
from app.db.repository import get_repository
from app.main import app
from app.orchestration.pipeline import ExtractionPipeline


def _make_pdf(path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Invoice")
    page.insert_text((72, 110), "Invoice No: INV-1023")
    page.insert_text((72, 150), "Revenue increased by 15%")
    doc.save(path)
    doc.close()


def test_upload_and_extract_digital_pdf(isolated_env, tmp_path):
    get_settings.cache_clear()
    pdf_path = tmp_path / "invoice.pdf"
    _make_pdf(pdf_path)

    client = TestClient(app)
    response = client.post(
        "/documents",
        files={"file": ("invoice.pdf", pdf_path.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    document_id = payload["document_id"]
    job_id = payload["job_id"]
    assert payload["status"] == "QUEUED"

    ExtractionPipeline(repo=get_repository()).run(document_id, job_id)

    status = client.get(f"/documents/{document_id}")
    assert status.status_code == 200
    assert status.json()["document"]["status"] in {"COMPLETED", "PARTIAL_SUCCESS"}

    representation = client.get(f"/documents/{document_id}/representation")
    assert representation.status_code == 200
    body = representation.json()
    assert body["document"]["page_count"] == 1
    texts = []
    for page in body["pages"]:
        for region in page["regions"]:
            element = region.get("element") or {}
            content = element.get("content") or {}
            if content.get("text"):
                texts.append(content["text"])
    blob = " ".join(texts)
    assert "INV-1023" in blob or "Invoice" in blob
