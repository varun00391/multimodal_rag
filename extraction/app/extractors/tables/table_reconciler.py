from __future__ import annotations

from app.models.table import TableModel
from app.validation.reconciliation import reconcile_text_values


def table_to_text(table: TableModel) -> str:
    lines = []
    if table.headers:
        lines.append(" | ".join(table.headers))
    for row in table.rows:
        lines.append(" | ".join(row))
    return "\n".join(lines).strip()


def reconcile_tables(primary: TableModel | None, secondary: TableModel | None) -> dict:
    if primary is None and secondary is None:
        return {"status": "CONFLICT", "candidates": []}
    if secondary is None:
        return {
            "status": "AGREED",
            "table": primary,
            "sources": ["pymupdf"],
        }
    if primary is None:
        return {
            "status": "AGREED",
            "table": secondary,
            "sources": ["ocr"],
        }
    comparison = reconcile_text_values(
        [
            {"value": table_to_text(primary), "source": "pymupdf"},
            {"value": table_to_text(secondary), "source": "ocr"},
        ]
    )
    chosen = primary if primary.row_count >= secondary.row_count else secondary
    comparison["table"] = chosen
    return comparison
