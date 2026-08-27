import hashlib
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.config import Settings
from app.errors import InputValidationError


PDF_SIGNATURE = b"%PDF-"
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/acrobat",
    "applications/vnd.pdf",
    "text/pdf",
    "text/x-pdf",
}


@dataclass(frozen=True)
class PdfValidationResult:
    sha256: str
    page_count: int
    size_bytes: int
    metadata: dict[str, float | int]


class InputValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate_upload_bytes(
        self,
        content: bytes,
        *,
        content_type: str | None,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> PdfValidationResult:
        if not content:
            raise InputValidationError("EMPTY_FILE", "Uploaded file is empty.")

        max_bytes = self._settings.extraction_max_file_bytes
        if len(content) > max_bytes:
            raise InputValidationError(
                "FILE_TOO_LARGE",
                f"Uploaded file exceeds the maximum size of {max_bytes} bytes.",
                details={"size_bytes": len(content), "max_bytes": max_bytes},
            )

        if not content.startswith(PDF_SIGNATURE):
            raise InputValidationError(
                "INVALID_PDF_SIGNATURE",
                "Uploaded file is not a valid PDF.",
            )

        if content_type and content_type.split(";", 1)[0].strip().lower() not in ALLOWED_CONTENT_TYPES:
            raise InputValidationError(
                "INVALID_CONTENT_TYPE",
                "Uploaded file must use an application/pdf content type.",
                details={"content_type": content_type},
            )

        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise InputValidationError(
                "PDF_PARSE_FAILED",
                "Uploaded file could not be opened as a PDF.",
                details={"reason": str(exc)},
            ) from exc

        try:
            page_count = document.page_count
            if page_count == 0:
                raise InputValidationError("PDF_HAS_NO_PAGES", "Uploaded PDF contains no pages.")

            if page_count > self._settings.extraction_max_pages:
                raise InputValidationError(
                    "TOO_MANY_PAGES",
                    f"Uploaded PDF exceeds the maximum of {self._settings.extraction_max_pages} pages.",
                    details={
                        "page_count": page_count,
                        "max_pages": self._settings.extraction_max_pages,
                    },
                )

            resolved_start, resolved_end = self._resolve_page_range(
                page_count,
                page_start=page_start,
                page_end=page_end,
            )

            max_page_points = self._settings.extraction_max_page_points
            max_rendered_pixels = self._settings.extraction_max_rendered_pixels

            for page_index in range(resolved_start - 1, resolved_end):
                page = document.load_page(page_index)
                width, height = page.rect.width, page.rect.height
                if width <= 0 or height <= 0:
                    raise InputValidationError(
                        "INVALID_PAGE_DIMENSIONS",
                        f"Page {page_index + 1} has invalid dimensions.",
                        details={"page": page_index + 1},
                    )
                if width > max_page_points or height > max_page_points:
                    raise InputValidationError(
                        "PAGE_DIMENSIONS_TOO_LARGE",
                        f"Page {page_index + 1} exceeds the maximum page dimension limit.",
                        details={
                            "page": page_index + 1,
                            "width": width,
                            "height": height,
                            "max_page_points": max_page_points,
                        },
                    )

                rendered_pixels = int(width * height)
                if rendered_pixels > max_rendered_pixels:
                    raise InputValidationError(
                        "RENDERED_PIXEL_LIMIT_EXCEEDED",
                        f"Page {page_index + 1} exceeds the rendered pixel limit.",
                        details={
                            "page": page_index + 1,
                            "rendered_pixels": rendered_pixels,
                            "max_rendered_pixels": max_rendered_pixels,
                        },
                    )

            sha256 = hashlib.sha256(content).hexdigest()
            return PdfValidationResult(
                sha256=sha256,
                page_count=page_count,
                size_bytes=len(content),
                metadata={
                    "selected_page_start": resolved_start,
                    "selected_page_end": resolved_end,
                },
            )
        finally:
            document.close()

    def _resolve_page_range(
        self,
        page_count: int,
        *,
        page_start: int | None,
        page_end: int | None,
    ) -> tuple[int, int]:
        start = 1 if page_start is None else page_start
        end = page_count if page_end is None else page_end

        if start < 1 or end < 1:
            raise InputValidationError(
                "INVALID_PAGE_RANGE",
                "Page range values must be greater than or equal to 1.",
            )
        if start > end:
            raise InputValidationError(
                "INVALID_PAGE_RANGE",
                "page_start must be less than or equal to page_end.",
            )
        if start > page_count or end > page_count:
            raise InputValidationError(
                "PAGE_RANGE_OUT_OF_BOUNDS",
                "Requested page range exceeds the PDF page count.",
                details={"page_count": page_count, "page_start": start, "page_end": end},
            )
        return start, end


class WorkspaceManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_workspace(
        self,
        *,
        document_id: str,
        pdf_bytes: bytes,
    ) -> Path:
        workspace = self._settings.extraction_output_dir / document_id
        if workspace.exists():
            source_path = workspace / "source.pdf"
            if not source_path.is_file():
                raise InputValidationError(
                    "WORKSPACE_CORRUPT",
                    "Existing workspace is missing source.pdf.",
                    details={"document_id": document_id},
                )
            return workspace

        workspace.mkdir(parents=True, exist_ok=False)
        for relative in (
            "raw",
            "assets/pages",
            "assets/tables",
            "assets/pictures",
            "assets/charts",
        ):
            (workspace / relative).mkdir(parents=True, exist_ok=True)

        internal_name = f"{secrets.token_hex(16)}.pdf"
        source_path = workspace / "source.pdf"
        temp_path = workspace / "raw" / internal_name
        temp_path.write_bytes(pdf_bytes)
        shutil.move(str(temp_path), str(source_path))
        return workspace

    def document_json_path(self, workspace_path: Path) -> Path:
        return workspace_path / "document.json"

    def report_json_path(self, workspace_path: Path) -> Path:
        return workspace_path / "extraction-report.json"

    def asset_path(self, workspace_path: Path, asset_path: str) -> Path:
        normalized = asset_path.strip().lstrip("/")
        if not normalized or ".." in normalized.split("/"):
            raise InputValidationError(
                "INVALID_ASSET_PATH",
                "Asset path is invalid.",
                details={"asset_path": asset_path},
            )

        candidate = (workspace_path / normalized).resolve()
        workspace = workspace_path.resolve()
        assets_root = (workspace / "assets").resolve()
        if assets_root not in candidate.parents and candidate != assets_root:
            raise InputValidationError(
                "INVALID_ASSET_PATH",
                "Asset path must stay within the workspace assets directory.",
                details={"asset_path": asset_path},
            )
        return candidate
