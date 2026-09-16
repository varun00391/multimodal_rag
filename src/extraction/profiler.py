from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from extraction.detect import PDF, PPTX, XLS, XLSX, detect_media_type, family_for
from extraction.settings import Settings


@dataclass
class Profile:
    media_type: str
    family: str
    page_count: int | None = None
    slide_count: int | None = None
    sheet_count: int | None = None
    pdf_page_routes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "media_type": self.media_type,
            "family": self.family,
            "page_count": self.page_count,
            "slide_count": self.slide_count,
            "sheet_count": self.sheet_count,
            "pdf_page_routes": self.pdf_page_routes,
        }


def _pdf_page_route(page: pymupdf.Page, threshold: int) -> str:
    text = (page.get_text("text") or "").strip()
    if len(text) >= threshold:
        return "pymupdf"
    return "paddleocr"


def profile_document(settings: Settings, path: Path, filename: str) -> Profile:
    media_type = detect_media_type(path, filename)
    family = family_for(media_type)
    profile = Profile(media_type=media_type, family=family)
    if media_type == PDF:
        with pymupdf.open(path) as doc:
            profile.page_count = doc.page_count
            profile.pdf_page_routes = [
                _pdf_page_route(page, settings.sparse_pdf_char_threshold) for page in doc
            ]
    elif media_type == PPTX:
        from pptx import Presentation

        profile.slide_count = len(Presentation(path).slides)
    elif media_type in {XLSX, XLS}:
        import pandas as pd

        excel = pd.ExcelFile(path)
        profile.sheet_count = len(excel.sheet_names)
    return profile
