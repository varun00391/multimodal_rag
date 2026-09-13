import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Chunk, Document, User
from app.services.ingestion import chunk_text, detect_modality, extra_dump, extract_text

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _serialize(doc: Document, chunk_count: int | None = None) -> dict:
    return {
        "id": doc.id,
        "filename": doc.original_name,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "modality": doc.modality,
        "source": doc.source,
        "status": doc.status,
        "extra": json.loads(doc.extra_json or "{}"),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "chunk_count": chunk_count,
    }


@router.get("")
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    out = []
    for doc in docs:
        count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()
        out.append(_serialize(doc, count))
    return out


@router.post("/upload")
async def upload(
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    max_bytes = settings.max_upload_mb * 1024 * 1024
    saved = []
    dest_root = settings.upload_dir / str(user.id)
    dest_root.mkdir(parents=True, exist_ok=True)
    for file in files:
        data = await file.read()
        if len(data) > max_bytes:
            raise HTTPException(status_code=413, detail=f"{file.filename} exceeds {settings.max_upload_mb}MB")
        name = file.filename or "untitled"
        stored = f"{uuid.uuid4().hex}{Path(name).suffix}"
        path = dest_root / stored
        path.write_bytes(data)
        mime = file.content_type or "application/octet-stream"
        modality = detect_modality(name, mime)
        text, meta = extract_text(name, mime, data)
        pieces = chunk_text(text) or [f"File {name} uploaded with no extractable text."]
        doc = Document(
            user_id=user.id,
            filename=stored,
            original_name=name,
            mime_type=mime,
            size_bytes=len(data),
            modality=modality,
            source="upload",
            status="ready",
            extra_json=extra_dump(meta),
        )
        db.add(doc)
        db.flush()
        for i, piece in enumerate(pieces):
            db.add(
                Chunk(
                    document_id=doc.id,
                    user_id=user.id,
                    content=piece,
                    chunk_index=i,
                    modality=modality,
                )
            )
        saved.append(_serialize(doc, len(pieces)))
    db.commit()
    return {"documents": saved}


@router.delete("/{doc_id}")
def delete_document(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    stored = settings.upload_dir / str(user.id) / doc.filename
    if stored.exists() and stored.is_file():
        stored.unlink()
    db.delete(doc)
    db.commit()
    return {"ok": True}
