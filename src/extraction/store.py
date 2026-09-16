from __future__ import annotations

import json
from pathlib import Path

from extraction.models.cdr import CanonicalDocument
from extraction.models.report import ExtractionReport


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_document(workspace_dir: Path, document: CanonicalDocument) -> Path:
    path = workspace_dir / "document.json"
    write_json(path, document.model_dump(mode="json"))
    return path


def save_report(workspace_dir: Path, report: ExtractionReport) -> Path:
    path = workspace_dir / "report.json"
    write_json(path, report.model_dump(mode="json"))
    return path


def save_inspection(workspace_dir: Path, inspection: dict) -> Path:
    path = workspace_dir / "inspection.json"
    write_json(path, inspection)
    return path


def load_document(workspace_dir: Path) -> CanonicalDocument | None:
    path = workspace_dir / "document.json"
    if not path.is_file():
        return None
    return CanonicalDocument.model_validate(read_json(path))


def load_report(workspace_dir: Path) -> ExtractionReport | None:
    path = workspace_dir / "report.json"
    if not path.is_file():
        return None
    return ExtractionReport.model_validate(read_json(path))


def resolve_under(root: Path, relative: str) -> Path:
    base = root.resolve()
    target = (base / relative).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Asset path escapes document directory.")
    return target
