from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from extraction.errors import ExtractionError
from extraction.settings import Settings

SAFE_FILENAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


@dataclass(frozen=True)
class IntakeResult:
    document_id: str
    original_path: Path
    filename: str
    size_bytes: int
    sha256: str
    workspace_dir: Path


def sanitize_filename(name: str) -> str:
    raw = Path(name).name or "upload"
    cleaned = "".join(ch if ch in SAFE_FILENAME_CHARS else "_" for ch in raw)
    return cleaned or "upload"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def document_dir(settings: Settings, document_id: str) -> Path:
    return settings.workspace / document_id


def intake_file(settings: Settings, source_path: Path, original_filename: str) -> IntakeResult:
    if not source_path.is_file():
        raise ExtractionError("EMPTY_FILE", "Upload is not a file.")
    size_bytes = source_path.stat().st_size
    if size_bytes <= 0:
        raise ExtractionError("EMPTY_FILE", "Uploaded file is empty.")
    if size_bytes > settings.max_upload_bytes:
        raise ExtractionError(
            "FILE_TOO_LARGE",
            f"File exceeds {settings.max_upload_bytes} bytes.",
        )
    checksum = sha256_file(source_path)
    filename = sanitize_filename(original_filename)
    workspace_dir = document_dir(settings, checksum)
    original_dir = workspace_dir / "original"
    assets_dir = workspace_dir / "assets"
    original_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    stored = original_dir / filename
    if source_path.resolve() != stored.resolve():
        shutil.copyfile(source_path, stored)
    return IntakeResult(
        document_id=checksum,
        original_path=stored,
        filename=filename,
        size_bytes=size_bytes,
        sha256=checksum,
        workspace_dir=workspace_dir,
    )
