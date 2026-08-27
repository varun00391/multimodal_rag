from pathlib import Path
from typing import Protocol

from app.models.canonical import CanonicalExtractionResult
from app.models.routing import ExtractionTask


class ExtractionAdapter(Protocol):
    name: str

    async def extract(
        self,
        pdf_path: Path,
        pages: list[int],
        tasks: list[ExtractionTask],
        context_pages: list[int] | None = None,
    ) -> CanonicalExtractionResult:
        ...
