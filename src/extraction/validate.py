from __future__ import annotations

from extraction.models.cdr import CanonicalDocument, Diagnostic
from extraction.models.report import ExtractionReport


def validate_document(document: CanonicalDocument) -> list[Diagnostic]:
    issues: list[Diagnostic] = []
    if document.unit_count != len(document.units):
        issues.append(
            Diagnostic(
                code="UNIT_COUNT_MISMATCH",
                message="unit_count does not match units length.",
            )
        )
    if not document.units and document.status != "failed":
        issues.append(Diagnostic(code="NO_UNITS", message="Document has no extracted units."))
    for unit in document.units:
        if unit.error:
            continue
        if not unit.elements:
            issues.append(
                Diagnostic(
                    code="EMPTY_UNIT",
                    message=f"{unit.unit_type} {unit.index} has no elements.",
                    unit_index=unit.index,
                )
            )
        seen = set()
        for element in unit.elements:
            if element.element_id in seen:
                issues.append(
                    Diagnostic(
                        code="DUPLICATE_ELEMENT_ID",
                        message=element.element_id,
                        unit_index=unit.index,
                    )
                )
            seen.add(element.element_id)
    return issues


def attach_validation(document: CanonicalDocument, report: ExtractionReport) -> CanonicalDocument:
    extra = validate_document(document)
    if not extra:
        return document
    document.diagnostics.extend(extra)
    for item in extra:
        report.warnings.append(f"{item.code}: {item.message}")
    if document.status == "completed":
        document.status = "completed_with_warnings"
    return document
