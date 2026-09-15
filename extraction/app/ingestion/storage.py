from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DocumentPaths:
    root: Path
    original: Path
    artifacts: Path
    pages: Path
    regions: Path
    images: Path
    figures: Path
    tables: Path
    ocr: Path
    validation: Path
    native: Path

    @property
    def document_json(self) -> Path:
        return self.artifacts / "document.json"

    @property
    def document_md(self) -> Path:
        return self.artifacts / "document.md"

    @property
    def profile_json(self) -> Path:
        return self.artifacts / "profile.json"


class LocalStorage:
    def __init__(self, root: Path | None = None):
        settings = get_settings()
        if settings.storage_backend.lower() == "s3":
            logger.warning("S3 storage is reserved in .env but not wired yet; using local STORAGE_ROOT.")
        self.root = root or settings.storage_root_path
        self.root.mkdir(parents=True, exist_ok=True)

    def document_paths(self, document_id: str) -> DocumentPaths:
        root = self.root / document_id
        artifacts = root / "artifacts"
        paths = DocumentPaths(
            root=root,
            original=root / "original.pdf",
            artifacts=artifacts,
            pages=artifacts / "pages",
            regions=artifacts / "regions",
            images=artifacts / "images",
            figures=artifacts / "figures",
            tables=artifacts / "tables",
            ocr=artifacts / "ocr",
            validation=artifacts / "validation",
            native=artifacts / "native",
        )
        for directory in (
            paths.root,
            paths.artifacts,
            paths.pages,
            paths.regions,
            paths.images,
            paths.figures,
            paths.tables,
            paths.ocr,
            paths.validation,
            paths.native,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return paths

    def save_original(self, document_id: str, data: bytes) -> Path:
        paths = self.document_paths(document_id)
        paths.original.write_bytes(data)
        return paths.original

    def write_bytes(self, path: Path, data: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write_text(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def exists(self, document_id: str) -> bool:
        return (self.root / document_id / "original.pdf").exists()


def get_storage() -> LocalStorage:
    return LocalStorage()
