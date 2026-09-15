from __future__ import annotations

import json
from pathlib import Path

from app.models.document import CanonicalDocument


def write_json_asset(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_document_json(path: Path, document: CanonicalDocument) -> Path:
    return write_json_asset(path, document.model_dump())
