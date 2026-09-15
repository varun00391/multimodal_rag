from __future__ import annotations

from pathlib import Path

import fitz

from app.core.config import get_settings
from app.models.common import pdf_bbox_to_px
from app.models.table import TableCell, TableModel
from app.profiling.pdf_profiler import open_pdf


def find_table_bboxes(page: fitz.Page) -> list[list[float]]:
    try:
        finder = page.find_tables()
    except Exception:
        return []
    tables = getattr(finder, "tables", finder) or []
    bboxes: list[list[float]] = []
    for table in tables:
        bbox = getattr(table, "bbox", None)
        if bbox is None:
            continue
        bboxes.append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])])
    return bboxes


def extract_tables_from_page(page: fitz.Page, page_number: int, dpi: int | None = None) -> list[TableModel]:
    settings = get_settings()
    dpi = dpi or settings.render_dpi
    try:
        finder = page.find_tables()
    except Exception:
        return []
    tables = getattr(finder, "tables", finder) or []
    models: list[TableModel] = []
    for index, table in enumerate(tables, start=1):
        bbox_raw = getattr(table, "bbox", [0, 0, 0, 0])
        bbox_pdf = [float(bbox_raw[0]), float(bbox_raw[1]), float(bbox_raw[2]), float(bbox_raw[3])]
        try:
            rows = table.extract() or []
        except Exception:
            rows = []
        headers = [str(cell or "").strip() for cell in (rows[0] if rows else [])]
        body = [[str(cell or "").strip() for cell in row] for row in rows[1:]]
        cells: list[TableCell] = []
        table_cells = getattr(table, "cells", None) or []
        row_count = int(getattr(table, "row_count", None) or len(rows))
        col_count = int(
            getattr(table, "col_count", None) or max((len(row) for row in rows), default=0)
        )
        if table_cells and col_count:
            for idx, cell in enumerate(table_cells):
                if cell is None:
                    continue
                r_i = idx // col_count
                c_i = idx % col_count
                if hasattr(cell, "x0"):
                    cell_bbox = [float(cell.x0), float(cell.y0), float(cell.x1), float(cell.y1)]
                elif isinstance(cell, (list, tuple)) and len(cell) >= 4:
                    cell_bbox = [float(cell[0]), float(cell[1]), float(cell[2]), float(cell[3])]
                else:
                    cell_bbox = []
                text = ""
                if r_i < len(rows) and c_i < len(rows[r_i]):
                    text = str(rows[r_i][c_i] or "").strip()
                cells.append(
                    TableCell(
                        row=r_i,
                        col=c_i,
                        text=text,
                        bbox=pdf_bbox_to_px(cell_bbox, dpi) if cell_bbox else [],
                        is_header=r_i == 0,
                    )
                )
        else:
            for r_i, row in enumerate(rows):
                for c_i, value in enumerate(row):
                    cells.append(
                        TableCell(
                            row=r_i,
                            col=c_i,
                            text=str(value or "").strip(),
                            is_header=r_i == 0,
                        )
                    )
        empty_ratio = 0.0
        if cells:
            empty_ratio = sum(1 for cell in cells if not cell.text) / len(cells)
        is_complex = empty_ratio > 0.25 or any(
            (cell.row_span > 1 or cell.col_span > 1) for cell in cells
        )
        models.append(
            TableModel(
                id=f"table_p{page_number:04d}_{index:02d}",
                page=page_number,
                bbox=pdf_bbox_to_px(bbox_pdf, dpi),
                headers=headers,
                rows=body,
                cells=cells,
                row_count=row_count,
                col_count=col_count,
                is_complex=is_complex,
            )
        )
    return models


def extract_tables(pdf_path: Path) -> dict[int, list[TableModel]]:
    doc = open_pdf(pdf_path)
    try:
        return {
            index + 1: extract_tables_from_page(doc.load_page(index), index + 1)
            for index in range(doc.page_count)
        }
    finally:
        doc.close()
