from __future__ import annotations

from pathlib import Path

from extraction.detect import CSV, DOCX, PPTX, TSV, XLS, XLSX
from extraction.errors import ExtractionError
from extraction.extractors.archive import unpack_zip
from extraction.extractors.audio import extract_audio
from extraction.extractors.image import extract_image
from extraction.extractors.office import extract_docx, extract_pptx
from extraction.extractors.pdf import extract_pdf
from extraction.extractors.tabular import extract_delimited, extract_excel
from extraction.extractors.video import extract_video
from extraction.models.cdr import Diagnostic, Unit
from extraction.models.report import ExtractionReport
from extraction.profiler import Profile
from extraction.settings import Settings


def dispatch(
    settings: Settings,
    path: Path,
    filename: str,
    profile: Profile,
    assets_dir: Path,
    report: ExtractionReport,
    diagnostics: list[Diagnostic],
    depth: int = 0,
) -> list[Unit]:
    family = profile.family
    if family == "pdf":
        return extract_pdf(settings, path, assets_dir, profile.pdf_page_routes, report, diagnostics)
    if family == "office":
        if profile.media_type == DOCX:
            return extract_docx(path, assets_dir, report, diagnostics)
        if profile.media_type == PPTX:
            return extract_pptx(path, assets_dir, report, diagnostics)
    if family == "tabular":
        if profile.media_type in {CSV, TSV}:
            return extract_delimited(settings, path, profile.media_type, report, diagnostics)
        if profile.media_type in {XLSX, XLS}:
            return extract_excel(settings, path, report, diagnostics)
    if family == "image":
        return extract_image(settings, path, assets_dir, report, diagnostics)
    if family == "audio":
        return extract_audio(settings, path, report, diagnostics)
    if family == "video":
        return extract_video(settings, path, assets_dir, report, diagnostics)
    if family == "archive":
        if depth >= settings.zip_max_depth:
            raise ExtractionError("ZIP_DEPTH", f"Zip nesting exceeds {settings.zip_max_depth}.")
        unpacked = assets_dir / f"unpacked-{depth}"
        children = unpack_zip(settings, path, unpacked)
        units: list[Unit] = []
        from extraction.profiler import profile_document

        for child in children:
            child_profile = profile_document(settings, child, child.name)
            child_assets = unpacked / f"{child.stem}-assets"
            child_assets.mkdir(parents=True, exist_ok=True)
            child_units = dispatch(
                settings,
                child,
                child.name,
                child_profile,
                child_assets,
                report,
                diagnostics,
                depth=depth + 1,
            )
            for unit in child_units:
                for element in unit.elements:
                    if not element.asset_path:
                        continue
                    candidate = child_assets / element.asset_path
                    if candidate.is_file():
                        element.asset_path = str(candidate.relative_to(assets_dir))
            units.extend(child_units)
        if not units:
            diagnostics.append(Diagnostic(code="ZIP_EMPTY", message="Zip contained no extractable files."))
        return units
    raise ExtractionError("UNSUPPORTED_TYPE", f"No extractor for {filename} ({profile.media_type}).")
