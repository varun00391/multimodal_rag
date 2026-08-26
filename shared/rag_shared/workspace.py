from __future__ import annotations

import shutil
from pathlib import Path


def workspace_root(upload_dir: str) -> Path:
    return Path(upload_dir) / "workspaces"


def document_rag_dir(upload_dir: str, document_id: str) -> Path:
    return workspace_root(upload_dir) / document_id / "rag"


def prepare_document_pdf(document_id: str, storage_path: str, upload_dir: str) -> tuple[Path, Path]:
    root = workspace_root(upload_dir)
    doc_dir = root / document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = doc_dir / f"{document_id}.pdf"
    shutil.copy2(storage_path, pdf_path)
    return root, pdf_path


def remove_document_workspace(document_id: str, upload_dir: str) -> None:
    doc_dir = workspace_root(upload_dir) / document_id
    if doc_dir.exists():
        shutil.rmtree(doc_dir)
