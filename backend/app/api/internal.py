from fastapi import APIRouter

router = APIRouter(prefix="/internal/v1", tags=["internal"])


@router.post("/extraction/extract")
async def extract_document(payload: dict) -> dict:
    return {"status": "not_implemented", "input": payload}


@router.get("/extraction/documents/{document_id}")
async def get_extraction_result(document_id: str) -> dict:
    return {"document_id": document_id, "status": "not_implemented"}


@router.post("/indexing/chunk")
async def chunk_document(payload: dict) -> dict:
    return {"status": "not_implemented", "input": payload}


@router.post("/indexing/embed")
async def embed_chunks(payload: dict) -> dict:
    return {"status": "not_implemented", "input": payload}


@router.post("/indexing/upsert")
async def upsert_index(payload: dict) -> dict:
    return {"status": "not_implemented", "input": payload}


@router.delete("/indexing/documents/{document_id}", status_code=204)
async def delete_index_artifacts(document_id: str) -> None:
    return None


@router.post("/retrieval/hybrid")
async def hybrid_retrieval(payload: dict) -> dict:
    return {"status": "not_implemented", "input": payload}


@router.post("/generation/answer")
async def generate_answer(payload: dict) -> dict:
    return {"status": "not_implemented", "input": payload}
