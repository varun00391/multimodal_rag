from __future__ import annotations

from extraction.models.cdr import CanonicalDocument, Diagnostic, Unit


def decide_status(units: list[Unit], diagnostics: list[Diagnostic]) -> str:
    if not units:
        return "failed"
    if any(unit.error for unit in units) or any(item.code.endswith("FAILED") for item in diagnostics):
        if all(unit.error for unit in units):
            return "failed"
        return "completed_with_warnings"
    if diagnostics:
        return "completed_with_warnings"
    return "completed"


def build_document(
    *,
    document_id: str,
    filename: str,
    media_type: str,
    sha256: str,
    size_bytes: int,
    stored_path: str,
    units: list[Unit],
    diagnostics: list[Diagnostic],
) -> CanonicalDocument:
    status = decide_status(units, diagnostics)
    return CanonicalDocument(
        document_id=document_id,
        source={
            "filename": filename,
            "media_type": media_type,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "stored_path": stored_path,
        },
        status=status,
        unit_count=len(units),
        units=units,
        diagnostics=diagnostics,
    )
