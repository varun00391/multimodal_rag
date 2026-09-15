from __future__ import annotations

import re

from app.models.region import Region
from app.models.table import TableModel

NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def parse_number(text: str) -> float | None:
    match = NUMBER_RE.search(text.replace("₹", "").replace("$", "").replace("€", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def table_arithmetic_ok(table: TableModel) -> bool | None:
    if not table.rows or table.col_count < 3:
        return None
    headers = [h.lower() for h in table.headers]
    qty_i = next((i for i, h in enumerate(headers) if "qty" in h or "quantity" in h), None)
    price_i = next((i for i, h in enumerate(headers) if "price" in h or "rate" in h), None)
    total_i = next((i for i, h in enumerate(headers) if "total" in h or "amount" in h), None)
    if qty_i is None or price_i is None or total_i is None:
        return None
    ok = True
    checked = False
    for row in table.rows:
        if max(qty_i, price_i, total_i) >= len(row):
            continue
        qty = parse_number(row[qty_i])
        price = parse_number(row[price_i])
        total = parse_number(row[total_i])
        if qty is None or price is None or total is None:
            continue
        checked = True
        if abs(qty * price - total) > 0.05 * max(1.0, abs(total)):
            ok = False
    return ok if checked else None


def caption_near_visual(caption: Region, visual: Region, max_gap: float = 80) -> bool:
    if caption.page != visual.page:
        return False
    c, v = caption.bbox, visual.bbox
    vertical_gap = c[1] - v[3]
    return -10 <= vertical_gap <= max_gap


def figure_references(text: str) -> list[str]:
    found = re.findall(r"(?:figure|fig\.|table|chart)\s+\d+", text or "", flags=re.I)
    return [item.lower() for item in found]
