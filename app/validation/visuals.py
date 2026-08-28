from __future__ import annotations

from pathlib import Path

from app.models.canonical import CanonicalPage, ElementType
from app.models.inspection import PageInspection
from app.models.validation import ValidationFailure

VISUAL_TYPES = {ElementType.PICTURE, ElementType.CHART, ElementType.DIAGRAM}


def validate_visuals(
    page: CanonicalPage,
    inspection: PageInspection | None,
    *,
    workspace: Path | None = None,
) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    visuals = [element for element in page.elements if element.type in VISUAL_TYPES]
    expected_figures = bool(inspection and inspection.layout.figure_candidate_count >= 2)
    if expected_figures and not visuals:
        failures.append(
            ValidationFailure(
                code="EXPECTED_FIGURE_MISSING",
                message="Inspection found figure candidates but no visual element was extracted.",
                details={
                    "figure_candidate_count": inspection.layout.figure_candidate_count if inspection else 0
                },
            )
        )

    for element in visuals:
        if element.bbox is None or element.bbox.area <= 0:
            failures.append(
                ValidationFailure(
                    code="VISUAL_BBOX_INVALID",
                    message="Visual element is missing a usable bounding box.",
                    element_id=element.element_id,
                )
            )
        elif element.bbox.right > page.width + 1 or element.bbox.bottom > page.height + 1:
            failures.append(
                ValidationFailure(
                    code="VISUAL_BBOX_INVALID",
                    message="Visual bounding box does not align with the source page.",
                    element_id=element.element_id,
                )
            )

        if element.asset:
            asset_path = Path(element.asset)
            if workspace is not None:
                candidate = element.asset if asset_path.is_absolute() else workspace / element.asset
                if not Path(candidate).is_file():
                    failures.append(
                        ValidationFailure(
                            code="VISUAL_CROP_MISSING",
                            message="Visual crop file is missing or empty.",
                            element_id=element.element_id,
                            details={"asset": element.asset},
                        )
                    )
        elif element.type in {ElementType.CHART, ElementType.DIAGRAM}:
            failures.append(
                ValidationFailure(
                    code="VISUAL_CROP_MISSING",
                    message="Chart or diagram element has no crop asset.",
                    element_id=element.element_id,
                )
            )

        if element.type in {ElementType.CHART, ElementType.DIAGRAM} and not (element.text or "").strip():
            failures.append(
                ValidationFailure(
                    code="VISUAL_MEANING_MISSING",
                    message="Chart or diagram has no grounded description.",
                    element_id=element.element_id,
                )
            )
    return failures
