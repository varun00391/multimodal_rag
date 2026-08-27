from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from rag.ingest import ingest_pdf
from rag_shared.app_factory import create_service_app, verify_internal_token
from rag_shared.config import get_settings
from rag_shared.core.errors import AppError
from rag_shared.rag_env import ensure_rag_env
from rag_shared.schemas.internal import ExtractionRequest, ExtractionResponse
from rag_shared.workspace import document_rag_dir

internal = APIRouter(tags=["internal"], dependencies=[Depends(verify_internal_token)])


@internal.post("/extraction/extract", response_model=ExtractionResponse)
def extract_document(payload: ExtractionRequest) -> ExtractionResponse:
    settings = get_settings()
    ensure_rag_env(settings)
    pdf_path = Path(payload.storage_path)
    workspace = Path(payload.upload_dir) / "workspaces"
    try:
        result = ingest_pdf(pdf_path, workspace)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            code="EXTRACTION_FAILED",
            message=f"Docling extraction failed: {exc}",
            status_code=500,
        ) from exc
    document_json = str(result["document_json"])
    rag_path = str(Path(document_json).parent / "rag")
    return ExtractionResponse(
        document_id=payload.document_id,
        document_json=document_json,
        rag_path=rag_path,
    )


@internal.get("/extraction/documents/{document_id}")
def get_extraction_result(document_id: str) -> dict:
    settings = get_settings()
    rag_path = document_rag_dir(settings.upload_dir, document_id)
    document_json = rag_path.parent / "document.json"
    return {
        "document_id": document_id,
        "status": "ready" if document_json.is_file() else "missing",
        "document_json": str(document_json),
        "rag_path": str(rag_path),
    }


app = create_service_app(service_name="extraction", internal_routers=[internal])
