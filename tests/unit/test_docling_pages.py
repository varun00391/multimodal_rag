import io
from pathlib import Path

import fitz

from app.adapters.docling_pages import (
    needs_sub_pdf,
    page_mapping,
    remap_page_number,
    write_sub_pdf,
)


def test_page_mapping_records_temporary_and_original_pages() -> None:
    mapping = page_mapping([8, 9])
    assert mapping == {"temporary_pages": [1, 2], "original_pages": [8, 9]}
    assert remap_page_number(1, mapping["original_pages"]) == 8
    assert remap_page_number(2, mapping["original_pages"]) == 9
    assert remap_page_number(0, mapping["original_pages"]) == 8
    assert remap_page_number(4, mapping["original_pages"]) is None


def test_needs_sub_pdf_only_when_selection_is_not_the_full_document() -> None:
    assert needs_sub_pdf([1, 2, 3], 3) is False
    assert needs_sub_pdf([2, 3], 3) is True
    assert needs_sub_pdf([1, 3], 3) is True


def test_write_sub_pdf_preserves_selected_page_order(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    document = fitz.open()
    for text in ("page-one", "page-two", "page-three"):
        page = document.new_page()
        page.insert_text((72, 72), text)
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    source.write_bytes(buffer.getvalue())

    destination = tmp_path / "raw" / "subset.pdf"
    write_sub_pdf(source, [3, 1], destination)

    subset = fitz.open(destination)
    try:
        assert subset.page_count == 2
        assert "page-three" in subset.load_page(0).get_text()
        assert "page-one" in subset.load_page(1).get_text()
    finally:
        subset.close()
