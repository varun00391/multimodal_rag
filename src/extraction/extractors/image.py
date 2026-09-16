from __future__ import annotations

from pathlib import Path

from extraction.clients.euron import describe_image
from extraction.elements import picture_element, text_element
from extraction.errors import ExtractionError
from extraction.extractors.ocr import ocr_image
from extraction.models.cdr import Diagnostic, Unit
from extraction.models.report import ExtractionReport, ModelCall, RouteRecord
from extraction.settings import Settings

VERSION = "1.0"
PROMPT_VERSION = "vlm-image-v1"


def extract_image(
    settings: Settings,
    path: Path,
    assets_dir: Path,
    report: ExtractionReport,
    diagnostics: list[Diagnostic],
) -> list[Unit]:
    dest = assets_dir / path.name
    if dest.resolve() != path.resolve():
        dest.write_bytes(path.read_bytes())

    text = ""
    confidence = None
    try:
        text, confidence = ocr_image(path)
    except ExtractionError as exc:
        diagnostics.append(Diagnostic(code=exc.code, message=exc.message, unit_index=1))

    if len(text.strip()) >= settings.image_ocr_char_threshold:
        report.routes.append(RouteRecord(unit_type="file", index=1, extractor="paddleocr"))
        report.model_calls.append(
            ModelCall(
                provider="euron",
                model=settings.euri_vlm_model,
                purpose="image",
                skipped=True,
                reason="OCR recovered enough text",
            )
        )
        return [
            Unit(
                unit_type="file",
                index=1,
                primary_route="paddleocr",
                elements=[
                    text_element(
                        unit_type="file",
                        unit_index=1,
                        order=1,
                        text=text,
                        extractor="paddleocr",
                        version=VERSION,
                        confidence=confidence,
                    ),
                    picture_element(
                        unit_type="file",
                        unit_index=1,
                        order=2,
                        asset_path=dest.name,
                        extractor="paddleocr",
                        version=VERSION,
                    ),
                ],
            )
        ]

    description = None
    try:
        description = describe_image(settings, path, report, purpose="image")
    except Exception as exc:
        diagnostics.append(Diagnostic(code="VLM_FAILED", message=str(exc), unit_index=1))
        report.model_calls.append(
            ModelCall(
                provider="euron",
                model=settings.euri_vlm_model,
                purpose="image",
                skipped=True,
                reason=str(exc),
            )
        )

    if description:
        report.routes.append(RouteRecord(unit_type="file", index=1, extractor="euron-vlm"))
        return [
            Unit(
                unit_type="file",
                index=1,
                primary_route="euron-vlm",
                elements=[
                    picture_element(
                        unit_type="file",
                        unit_index=1,
                        order=1,
                        asset_path=dest.name,
                        extractor="euron-vlm",
                        version=VERSION,
                        text=description,
                        model=settings.euri_vlm_model,
                        prompt_version=PROMPT_VERSION,
                    )
                ],
            )
        ]

    report.routes.append(RouteRecord(unit_type="file", index=1, extractor="image"))
    if text:
        elements = [
            text_element(
                unit_type="file",
                unit_index=1,
                order=1,
                text=text,
                extractor="paddleocr",
                version=VERSION,
                confidence=confidence,
            ),
            picture_element(
                unit_type="file",
                unit_index=1,
                order=2,
                asset_path=dest.name,
                extractor="paddleocr",
                version=VERSION,
            ),
        ]
        return [Unit(unit_type="file", index=1, primary_route="paddleocr", elements=elements)]

    diagnostics.append(
        Diagnostic(code="IMAGE_NO_TEXT", message="No OCR text and no VLM description.", unit_index=1)
    )
    return [
        Unit(
            unit_type="file",
            index=1,
            primary_route="image",
            elements=[
                picture_element(
                    unit_type="file",
                    unit_index=1,
                    order=1,
                    asset_path=dest.name,
                    extractor="image",
                    version=VERSION,
                )
            ],
        )
    ]
