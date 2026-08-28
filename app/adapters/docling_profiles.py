from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

PROFILE_DIGITAL_LAYOUT = "digital-layout"
PROFILE_DIGITAL_TABLE = "digital-table"
PROFILE_FORMULA_CODE = "formula-code"
PROFILE_PRIVATE_OCR = "private-ocr"

DEFAULT_PROFILE = PROFILE_DIGITAL_LAYOUT
PROFILE_VERSION = "1.0"

KNOWN_PROFILES = (
    PROFILE_DIGITAL_LAYOUT,
    PROFILE_DIGITAL_TABLE,
    PROFILE_FORMULA_CODE,
    PROFILE_PRIVATE_OCR,
)

PROFILE_TASK_KIND = {
    PROFILE_DIGITAL_LAYOUT: "layout",
    PROFILE_DIGITAL_TABLE: "table_structure",
    PROFILE_FORMULA_CODE: "formula_code",
    PROFILE_PRIVATE_OCR: "ocr",
}


@dataclass(frozen=True)
class DoclingProfileSpec:
    name: str
    version: str
    do_ocr: bool
    do_table_structure: bool
    do_code_enrichment: bool
    do_formula_enrichment: bool
    generate_page_images: bool


PROFILES: dict[str, DoclingProfileSpec] = {
    PROFILE_DIGITAL_LAYOUT: DoclingProfileSpec(
        name=PROFILE_DIGITAL_LAYOUT,
        version=PROFILE_VERSION,
        do_ocr=False,
        do_table_structure=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        generate_page_images=False,
    ),
    PROFILE_DIGITAL_TABLE: DoclingProfileSpec(
        name=PROFILE_DIGITAL_TABLE,
        version=PROFILE_VERSION,
        do_ocr=False,
        do_table_structure=True,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        generate_page_images=False,
    ),
    PROFILE_FORMULA_CODE: DoclingProfileSpec(
        name=PROFILE_FORMULA_CODE,
        version=PROFILE_VERSION,
        do_ocr=False,
        do_table_structure=True,
        do_code_enrichment=True,
        do_formula_enrichment=True,
        generate_page_images=False,
    ),
    PROFILE_PRIVATE_OCR: DoclingProfileSpec(
        name=PROFILE_PRIVATE_OCR,
        version=PROFILE_VERSION,
        do_ocr=True,
        do_table_structure=True,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        generate_page_images=False,
    ),
}


def require_profile(name: str) -> DoclingProfileSpec:
    if name not in PROFILES:
        known = ", ".join(KNOWN_PROFILES)
        raise ValueError(f"Unknown Docling profile '{name}'. Expected one of: {known}.")
    return PROFILES[name]


def parse_extractor_ref(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    extractor, _, profile = value.partition(":")
    extractor = extractor.strip().lower()
    profile = profile.strip() or None
    if not extractor:
        return None, None
    return extractor, profile


def resolve_docling_profile(force_extractor: str | None) -> str | None:
    extractor, profile = parse_extractor_ref(force_extractor)
    if extractor != "docling":
        return None
    if profile is None:
        return DEFAULT_PROFILE
    return require_profile(profile).name


def pipeline_flags(profile_name: str) -> dict[str, bool]:
    spec = require_profile(profile_name)
    return {
        "do_ocr": spec.do_ocr,
        "do_table_structure": spec.do_table_structure,
        "do_code_enrichment": spec.do_code_enrichment,
        "do_formula_enrichment": spec.do_formula_enrichment,
        "generate_page_images": spec.generate_page_images,
    }


def apply_docling_artifacts_path(settings: Settings) -> None:
    """Keep Docling's global settings in sync with our config.

    Docling reads ``DOCLING_ARTIFACTS_PATH`` itself. An empty env value becomes
    ``Path('.')`` (the process cwd). That is treated as a local model store and
    disables Hugging Face auto-download, which is what produced the
    ``docling-layout-heron`` FileNotFoundError in Docker.
    """
    try:
        from docling.datamodel.settings import settings as docling_settings
    except ImportError:
        return

    env_value = os.environ.get("DOCLING_ARTIFACTS_PATH")
    if env_value is not None and not env_value.strip():
        os.environ.pop("DOCLING_ARTIFACTS_PATH", None)

    artifacts = settings.docling_artifacts_path
    if artifacts is None:
        docling_settings.artifacts_path = None
    else:
        docling_settings.artifacts_path = Path(artifacts)


def build_pipeline_options(profile_name: str, settings: Settings):
    spec = require_profile(profile_name)
    try:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install project dependencies including the docling package."
        ) from exc

    apply_docling_artifacts_path(settings)
    options = PdfPipelineOptions()
    options.do_ocr = spec.do_ocr
    options.do_table_structure = spec.do_table_structure
    options.do_code_enrichment = spec.do_code_enrichment
    options.do_formula_enrichment = spec.do_formula_enrichment
    options.generate_page_images = (
        spec.generate_page_images or settings.docling_generate_page_images
    )
    options.generate_picture_images = settings.docling_generate_picture_images
    options.images_scale = settings.docling_image_scale
    if hasattr(options, "enable_remote_services"):
        options.enable_remote_services = False
    artifacts_path = settings.docling_artifacts_path
    if artifacts_path is not None:
        options.artifacts_path = str(artifacts_path)
    return options


def build_docling_converter(profile_name: str, settings: Settings):
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install project dependencies including the docling package."
        ) from exc

    options = build_pipeline_options(profile_name, settings)
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        }
    )


def docling_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("docling")
    except Exception:
        return None
