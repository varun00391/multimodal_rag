from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from app.extractors.text.ocr import OCRResult, ocr_image
from app.models.table import TableCell, TableModel


def extract_table_via_ocr(
    crop_path: Path,
    page_number: int,
    bbox_px: list[float],
    table_id: str,
) -> tuple[TableModel, OCRResult]:
    result = ocr_image(crop_path)
    rows_map: dict[int, list] = defaultdict(list)
    for word in result.words:
        y_mid = (word.bbox[1] + word.bbox[3]) / 2
        row_key = int(round(y_mid / 18.0))
        rows_map[row_key].append(word)
    ordered_keys = sorted(rows_map)
    grid: list[list[str]] = []
    cells: list[TableCell] = []
    for r_i, key in enumerate(ordered_keys):
        words = sorted(rows_map[key], key=lambda w: w.bbox[0])
        texts = [w.text for w in words]
        grid.append(texts)
        for c_i, word in enumerate(words):
            cells.append(
                TableCell(
                    row=r_i,
                    col=c_i,
                    text=word.text,
                    bbox=word.bbox,
                    is_header=r_i == 0,
                )
            )
    headers = grid[0] if grid else []
    body = grid[1:] if len(grid) > 1 else []
    model = TableModel(
        id=table_id,
        page=page_number,
        bbox=bbox_px,
        headers=headers,
        rows=body,
        cells=cells,
        row_count=len(grid),
        col_count=max((len(row) for row in grid), default=0),
        is_complex=False,
    )
    return model, result
