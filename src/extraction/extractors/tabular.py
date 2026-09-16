from __future__ import annotations

from pathlib import Path

import pandas as pd

from extraction.elements import table_element
from extraction.models.cdr import Diagnostic, Unit
from extraction.models.report import ExtractionReport, RouteRecord
from extraction.settings import Settings

VERSION = "1.0"


def _frame_to_unit(
    frame: pd.DataFrame,
    index: int,
    label: str,
    extractor: str,
    max_rows: int,
    diagnostics: list[Diagnostic],
) -> Unit:
    columns = [str(column) for column in frame.columns.tolist()]
    if len(frame) > max_rows:
        diagnostics.append(
            Diagnostic(
                code="TABLE_TRUNCATED",
                message=f"{label} truncated to {max_rows} rows.",
                unit_index=index,
            )
        )
        frame = frame.head(max_rows)
    rows = [["" if pd.isna(value) else str(value) for value in row] for row in frame.itertuples(index=False, name=None)]
    elements = []
    if columns or rows:
        elements.append(
            table_element(
                unit_type="sheet",
                unit_index=index,
                order=1,
                columns=columns,
                rows=rows,
                extractor=extractor,
                version=VERSION,
            )
        )
    return Unit(
        unit_type="sheet",
        index=index,
        label=label,
        primary_route=extractor,
        elements=elements,
        error=None if elements else "SHEET_EMPTY",
    )


def extract_delimited(
    settings: Settings,
    path: Path,
    media_type: str,
    report: ExtractionReport,
    diagnostics: list[Diagnostic],
) -> list[Unit]:
    sep = "\t" if media_type.endswith("tab-separated-values") or path.suffix.lower() == ".tsv" else ","
    extractor = "pandas"
    try:
        frame = pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)
    except UnicodeDecodeError:
        frame = pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False, encoding="latin-1")
    report.routes.append(RouteRecord(unit_type="sheet", index=1, extractor=extractor))
    return [_frame_to_unit(frame, 1, path.name, extractor, settings.max_table_rows, diagnostics)]


def extract_excel(
    settings: Settings,
    path: Path,
    report: ExtractionReport,
    diagnostics: list[Diagnostic],
) -> list[Unit]:
    extractor = "openpyxl+pandas"
    excel = pd.ExcelFile(path)
    units = []
    for index, sheet in enumerate(excel.sheet_names, start=1):
        frame = excel.parse(sheet, dtype=str, keep_default_na=False)
        report.routes.append(RouteRecord(unit_type="sheet", index=index, extractor=extractor))
        units.append(_frame_to_unit(frame, index, sheet, extractor, settings.max_table_rows, diagnostics))
    return units
