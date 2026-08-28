from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from app.adapters.docling_mapping import ADAPTER_VERSION as DOCLING_ADAPTER_VERSION
from app.adapters.gemini_adapter import ADAPTER_VERSION as GEMINI_ADAPTER_VERSION
from app.adapters.groq_vision_adapter import ADAPTER_VERSION as GROQ_ADAPTER_VERSION
from app.adapters.pymupdf_adapter import ADAPTER_VERSION as PYMUPDF_ADAPTER_VERSION
from app.config import Settings
from app.models.canonical import CanonicalExtractionResult
from app.models.inspection import DocumentInspection
from app.models.jobs import ExtractionPolicy
from app.models.routing import ExtractionGroup

logger = logging.getLogger(__name__)

CACHE_FORMAT_VERSION = "1"


def version_fingerprint(settings: Settings) -> dict[str, str]:
    return {
        "cache_format": CACHE_FORMAT_VERSION,
        "schema_version": settings.extraction_schema_version,
        "routing_policy_version": settings.extraction_routing_policy_version,
        "pymupdf_adapter": PYMUPDF_ADAPTER_VERSION,
        "docling_adapter": DOCLING_ADAPTER_VERSION,
        "gemini_adapter": GEMINI_ADAPTER_VERSION,
        "groq_adapter": GROQ_ADAPTER_VERSION,
        "gemini_model": settings.gemini_model_id,
        "gemini_prompt_version": str(settings.gemini_extraction_prompt_version),
        "groq_model": settings.groq_visual_model,
        "groq_prompt_version": str(settings.groq_visual_prompt_version),
        "docling_image_scale": str(settings.docling_image_scale),
    }


def fingerprint_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def policy_fingerprint(policy: ExtractionPolicy) -> str:
    return fingerprint_hash(policy.model_dump(mode="json"))


class ExtractionCache:
    """Version-aware filesystem cache for inspection, groups, and documents."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root = settings.resolved_cache_dir
        self.enabled = settings.extraction_cache_enabled

    def versions(self) -> dict[str, str]:
        return version_fingerprint(self._settings)

    def document_key(self, *, sha256: str, policy: ExtractionPolicy) -> str:
        return fingerprint_hash(
            {
                "kind": "document",
                "sha256": sha256,
                "policy": policy.model_dump(mode="json"),
                "versions": self.versions(),
            }
        )

    def inspection_key(self, *, sha256: str, page_start: int, page_end: int) -> str:
        return fingerprint_hash(
            {
                "kind": "inspection",
                "sha256": sha256,
                "page_start": page_start,
                "page_end": page_end,
                "versions": {
                    "schema_version": self._settings.extraction_schema_version,
                    "pymupdf_adapter": PYMUPDF_ADAPTER_VERSION,
                    "routing_policy_version": self._settings.extraction_routing_policy_version,
                },
            }
        )

    def group_key(self, group: ExtractionGroup) -> str:
        return fingerprint_hash(
            {
                "kind": "group",
                "document_id": group.document_id,
                "extractor": group.extractor,
                "profile": group.profile,
                "kind_name": group.kind,
                "pages": list(group.pages),
                "context_pages": list(group.context_pages),
                "options_hash": group.options_hash,
                "privacy_mode": group.privacy_mode,
                "tasks": [
                    {
                        "page": task.page,
                        "kind": task.kind,
                        "extractor": task.extractor,
                        "profile": task.profile,
                        "region": task.region,
                        "options_hash": task.options_hash,
                    }
                    for task in group.tasks
                ],
                "versions": self.versions(),
            }
        )

    def get_inspection(self, key: str) -> DocumentInspection | None:
        payload = self._read_json(self._inspection_path(key))
        if not payload:
            return None
        try:
            return DocumentInspection.model_validate(payload)
        except Exception:
            logger.warning("Discarding incompatible inspection cache entry %s", key)
            return None

    def put_inspection(self, key: str, inspection: DocumentInspection) -> None:
        self._write_json(self._inspection_path(key), inspection.model_dump(mode="json"))

    def get_group(self, key: str) -> CanonicalExtractionResult | None:
        payload = self._read_json(self._group_path(key))
        if not payload:
            return None
        try:
            return CanonicalExtractionResult.model_validate(payload)
        except Exception:
            logger.warning("Discarding incompatible group cache entry %s", key)
            return None

    def put_group(self, key: str, result: CanonicalExtractionResult) -> None:
        self._write_json(self._group_path(key), result.model_dump(mode="json"))

    def get_document(self, key: str) -> dict[str, Any] | None:
        directory = self._document_dir(key)
        manifest = self._read_json(directory / "manifest.json")
        if not manifest:
            return None
        if manifest.get("versions") != self.versions():
            return None
        document = self._read_json(directory / "document.json")
        report = self._read_json(directory / "extraction-report.json")
        inspection = self._read_json(directory / "inspection.json")
        routing = self._read_json(directory / "routing.json")
        if document is None or report is None or inspection is None:
            return None
        return {
            "document": document,
            "report": report,
            "inspection": inspection,
            "routing": routing or {},
            "status": manifest.get("status") or document.get("status"),
        }

    def put_document(
        self,
        key: str,
        *,
        document: dict[str, Any],
        report: dict[str, Any],
        inspection: dict[str, Any],
        routing: dict[str, Any],
        status: str,
    ) -> None:
        directory = self._document_dir(key)
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(directory / "document.json", document)
        self._write_json(directory / "extraction-report.json", report)
        self._write_json(directory / "inspection.json", inspection)
        self._write_json(directory / "routing.json", routing)
        self._write_json(
            directory / "manifest.json",
            {"versions": self.versions(), "status": status, "format": CACHE_FORMAT_VERSION},
        )

    def _inspection_path(self, key: str) -> Path:
        return self._root / "inspections" / f"{key}.json"

    def _group_path(self, key: str) -> Path:
        return self._root / "groups" / f"{key}.json"

    def _document_dir(self, key: str) -> Path:
        return self._root / "documents" / key

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not self.enabled or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to read cache file %s", path)
            return None
        return payload if isinstance(payload, dict) else None

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
