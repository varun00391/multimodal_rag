from __future__ import annotations

import time
from pathlib import Path

from extraction.canonicalize import build_document
from extraction.errors import ExtractionError
from extraction.intake import IntakeResult, intake_file
from extraction.models.cdr import CanonicalDocument, Diagnostic
from extraction.models.report import ExtractionReport
from extraction.profiler import profile_document
from extraction.router import dispatch
from extraction.settings import Settings
from extraction.store import save_document, save_inspection, save_report
from extraction.validate import attach_validation


def run_pipeline(
    settings: Settings,
    source_path: Path,
    filename: str,
    job_id: str,
    intake: IntakeResult | None = None,
) -> CanonicalDocument:
    started = time.perf_counter()
    intake = intake or intake_file(settings, source_path, filename)
    report = ExtractionReport(document_id=intake.document_id, job_id=job_id)
    diagnostics: list[Diagnostic] = []
    units = []
    media_type = "application/octet-stream"
    try:
        profile = profile_document(settings, intake.original_path, intake.filename)
        media_type = profile.media_type
        save_inspection(intake.workspace_dir, profile.to_dict())
        report.timings_ms["profile"] = round((time.perf_counter() - started) * 1000, 2)
        extract_started = time.perf_counter()
        units = dispatch(
            settings,
            intake.original_path,
            intake.filename,
            profile,
            intake.workspace_dir / "assets",
            report,
            diagnostics,
        )
        report.timings_ms["extract"] = round((time.perf_counter() - extract_started) * 1000, 2)
    except ExtractionError as exc:
        diagnostics.append(Diagnostic(code=exc.code, message=exc.message))
        report.warnings.append(f"{exc.code}: {exc.message}")
    stored_path = str(Path("original") / intake.filename)
    document = build_document(
        document_id=intake.document_id,
        filename=intake.filename,
        media_type=media_type,
        sha256=intake.sha256,
        size_bytes=intake.size_bytes,
        stored_path=stored_path,
        units=units,
        diagnostics=diagnostics,
    )
    document = attach_validation(document, report)
    report.timings_ms["total"] = round((time.perf_counter() - started) * 1000, 2)
    save_document(intake.workspace_dir, document)
    save_report(intake.workspace_dir, report)
    if document.status == "failed":
        raise ExtractionError(
            diagnostics[0].code if diagnostics else "EXTRACTION_FAILED",
            diagnostics[0].message if diagnostics else "Extraction failed.",
        )
    return document
