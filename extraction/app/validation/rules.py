from app.models.common import RegionType, ValidationStatus
from app.models.region import Region
from app.models.validation import ValidationResult


def needs_human_review(region: Region, validation: ValidationResult, threshold: float) -> bool:
    if validation.needs_review:
        return True
    if validation.status == ValidationStatus.CONFLICT:
        return True
    if validation.confidence < threshold:
        return True
    if region.type in {RegionType.COMPLEX_TABLE} and validation.confidence < 0.9:
        return True
    if not (region.element and (region.element.content.get("text") or region.element.content.get("table"))):
        if region.type in {RegionType.PARAGRAPH, RegionType.HEADING, RegionType.TABLE}:
            return True
    return False
