from __future__ import annotations

import re

from app.models.common import RegionType
from app.models.element import NativeObject
from app.models.page import PageProfile

HEADING_MAX_CHARS = 140
LIST_RE = re.compile(r"^\s*(?:[-*•●▪‣]|(\d+|[A-Za-z])[.)])\s+")
FOOTNOTE_RE = re.compile(r"^\s*(?:\d+|[ivxlcdm]+)[.)]\s+", re.I)


def classify_text_block(obj: NativeObject, page_profile: PageProfile) -> RegionType:
    text = ""
    if isinstance(obj.content, str):
        text = obj.content
    elif isinstance(obj.content, dict):
        text = str(obj.content.get("text") or "")
    text = text.strip()
    extra = obj.extra or {}
    font_size = float(extra.get("font_size") or extra.get("size") or 0)
    bbox = obj.bbox_pdf or obj.bbox
    y0 = bbox[1] if len(bbox) == 4 else 0
    y1 = bbox[3] if len(bbox) == 4 else 0
    page_h = page_profile.height or 1
    if y1 < page_h * 0.08 and len(text) < 80:
        return RegionType.HEADER
    if y0 > page_h * 0.92 and len(text) < 80:
        return RegionType.FOOTER
    if y0 > page_h * 0.82 and FOOTNOTE_RE.match(text) and font_size and font_size < 10:
        return RegionType.FOOTNOTE
    if text.lower().startswith(("figure ", "fig.", "table ", "chart ")):
        return RegionType.CAPTION
    if LIST_RE.match(text):
        return RegionType.LIST
    avg_size = extra.get("page_avg_font") or 11.0
    if font_size >= max(14.0, avg_size * 1.25) and len(text) <= HEADING_MAX_CHARS:
        return RegionType.HEADING
    if len(text) <= 60 and extra.get("is_bold") and font_size >= avg_size:
        return RegionType.HEADING
    return RegionType.PARAGRAPH
