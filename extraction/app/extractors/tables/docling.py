from __future__ import annotations

from pathlib import Path

from app.core.exceptions import TableExtractionFailedError
from app.models.table import TableCell, TableModel


def extract_with_docling(pdf_path: Path, page_number: int | None = None) -> list[TableModel]:
    try:
        from docling.document_converter import DocumentConverter
    except Exception as exc:
        raise TableExtractionFailedError(
            "Docling is not installed. Set TABLE_ENGINE=pymupdf or install docling."
        ) from exc
    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        document = result.document
    except Exception as exc:
        raise TableExtractionFailedError(f"Docling table extraction failed: {exc}") from exc

    tables: list[TableModel] = []
    items = getattr(document, "tables", None) or []
    for index, item in enumerate(items, start=1):
        page = page_number or getattr(item, "page_no", 1) or 1
        data = item.export_to_dataframe() if hasattr(item, "export_to_dataframe") else None
        headers: list[str] = []
        rows: list[list[str]] = []
        cells: list[TableCell] = []
        if data is not None:
            headers = [str(col) for col in data.columns.tolist()]
            for r_i, row in enumerate(data.itertuples(index=False), start=1):
                values = [str(v) for v in row]
                rows.append(values)
                for c_i, value in enumerate(values):
                    cells.append(TableCell(row=r_i, col=c_i, text=value, is_header=False))
            for c_i, header in enumerate(headers):
                cells.append(TableCell(row=0, col=c_i, text=header, is_header=True))
        bbox = [0.0, 0.0, 0.0, 0.0]
        prov = getattr(item, "prov", None)
        if prov:
            first = prov[0]
            bbox_obj = getattr(first, "bbox", None)
            if bbox_obj is not None:
                bbox = [
                    float(getattr(bbox_obj, "l", 0)),
                    float(getattr(bbox_obj, "t", 0)),
                    float(getattr(bbox_obj, "r", 0)),
                    float(getattr(bbox_obj, "b", 0)),
                ]
        tables.append(
            TableModel(
                id=f"docling_table_{index:02d}",
                page=int(page),
                bbox=bbox,
                headers=headers,
                rows=rows,
                cells=cells,
                row_count=len(rows) + (1 if headers else 0),
                col_count=len(headers) or max((len(r) for r in rows), default=0),
            )
        )
    return tables
