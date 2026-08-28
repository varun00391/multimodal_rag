from __future__ import annotations

import re

from app.models.canonical import CanonicalPage, ElementType
from app.models.inspection import PageInspection
from app.models.validation import ValidationFailure

SEPARATOR_RE = re.compile(r"^[\s|:-]+$")


def validate_tables(
    page: CanonicalPage,
    inspection: PageInspection | None,
) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    tables = [element for element in page.elements if element.type == ElementType.TABLE]
    expected = bool(
        inspection and (inspection.probable_complex_table or inspection.layout.table_candidate_count >= 2)
    )
    if expected and not tables:
        failures.append(
            ValidationFailure(
                code="TABLE_MISSING",
                message="Inspection found table candidates but no table element was extracted.",
                details={"table_candidate_count": inspection.layout.table_candidate_count if inspection else 0},
            )
        )

    for table in tables:
        cells_text = (table.text or "").strip()
        markdown = (table.markdown or "").strip()
        html = (table.html or "").strip()
        if not cells_text and not markdown and not html:
            failures.append(
                ValidationFailure(
                    code="TABLE_EMPTY",
                    message="Table element has no rows, cells, markdown, or HTML.",
                    element_id=table.element_id,
                )
            )
            continue

        if markdown:
            rows = _markdown_rows(markdown)
            if not rows:
                failures.append(
                    ValidationFailure(
                        code="TABLE_MARKDOWN_INVALID",
                        message="Table markdown is present but is not a consistent grid.",
                        element_id=table.element_id,
                    )
                )
            elif any(len(row) != len(rows[0]) for row in rows):
                failures.append(
                    ValidationFailure(
                        code="TABLE_STRUCTURE_INVALID",
                        message="Table markdown rows do not share a consistent column count.",
                        element_id=table.element_id,
                        details={"rows": len(rows), "cols": len(rows[0])},
                    )
                )
            elif len(rows) < 1 or len(rows[0]) < 1:
                failures.append(
                    ValidationFailure(
                        code="TABLE_EMPTY",
                        message="Table markdown has no usable rows or columns.",
                        element_id=table.element_id,
                    )
                )

        if html and "<table" not in html.lower() and "<tr" not in html.lower():
            failures.append(
                ValidationFailure(
                    code="TABLE_HTML_INVALID",
                    message="Table HTML is present but does not contain table markup.",
                    element_id=table.element_id,
                )
            )
    return failures


def markdown_table_shape(markdown: str) -> tuple[int, int] | None:
    rows = _markdown_rows(markdown)
    if not rows:
        return None
    width = len(rows[0])
    if width == 0:
        return None
    return len(rows), width


def _markdown_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            continue
        if SEPARATOR_RE.match(stripped.replace("|", "")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells:
            rows.append(cells)
    return rows
