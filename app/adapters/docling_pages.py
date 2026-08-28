from __future__ import annotations

from pathlib import Path

import fitz


def needs_sub_pdf(requested_pages: list[int], total_pages: int) -> bool:
    return requested_pages != list(range(1, total_pages + 1))


def page_mapping(requested_pages: list[int]) -> dict[str, list[int]]:
    return {
        "temporary_pages": list(range(1, len(requested_pages) + 1)),
        "original_pages": list(requested_pages),
    }


def remap_page_number(temporary_page: int, original_pages: list[int]) -> int | None:
    if 1 <= temporary_page <= len(original_pages):
        return original_pages[temporary_page - 1]
    if 0 <= temporary_page < len(original_pages):
        return original_pages[temporary_page]
    return None


def write_sub_pdf(source_pdf: Path, pages: list[int], destination: Path) -> Path:
    if not pages:
        raise ValueError("Cannot create a sub-PDF without page numbers.")

    source = fitz.open(source_pdf)
    output = fitz.open()
    try:
        for page_number in pages:
            index = page_number - 1
            if index < 0 or index >= source.page_count:
                raise ValueError(
                    f"Requested page {page_number} is outside the source PDF "
                    f"({source.page_count} pages)."
                )
            output.insert_pdf(source, from_page=index, to_page=index)
        destination.parent.mkdir(parents=True, exist_ok=True)
        output.save(destination)
    finally:
        output.close()
        source.close()
    return destination


def page_geometries(source_pdf: Path, pages: list[int]) -> dict[int, tuple[float, float, int]]:
    document = fitz.open(source_pdf)
    try:
        geometries: dict[int, tuple[float, float, int]] = {}
        for page_number in pages:
            page = document.load_page(page_number - 1)
            geometries[page_number] = (page.rect.width, page.rect.height, page.rotation)
        return geometries
    finally:
        document.close()
