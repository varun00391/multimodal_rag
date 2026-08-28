from app.adapters.docling_mapping import (
    canonical_bbox_from_docling,
    element_type_for_label,
    item_text,
    normalize_label,
)
from app.models.canonical import ElementType


class FakeBBox:
    def __init__(self, l: float, t: float, r: float, b: float, origin: str = "TOPLEFT") -> None:
        self.l = l
        self.t = t
        self.r = r
        self.b = b
        self.coord_origin = origin

    def to_top_left_origin(self, page_height: float) -> "FakeBBox":
        if "BOTTOM" in self.coord_origin.upper():
            return FakeBBox(self.l, page_height - self.t, self.r, page_height - self.b, "TOPLEFT")
        return self


def test_label_mapping_covers_layout_table_formula_and_ocr_types() -> None:
    assert element_type_for_label("section_header") == ElementType.HEADING
    assert element_type_for_label("paragraph") == ElementType.PARAGRAPH
    assert element_type_for_label("table") == ElementType.TABLE
    assert element_type_for_label("formula") == ElementType.FORMULA
    assert element_type_for_label("code") == ElementType.CODE
    assert element_type_for_label("list_item") == ElementType.LIST
    assert element_type_for_label("picture") == ElementType.PICTURE
    assert normalize_label("DocItemLabel.TABLE") == "table"


def test_bottom_left_bbox_converts_to_canonical_top_left() -> None:
    page_height = 792.0
    bbox = canonical_bbox_from_docling(
        FakeBBox(40, 700, 200, 650, origin="BOTTOMLEFT"),
        page_height,
    )
    assert bbox is not None
    assert bbox.coordinate_origin == "top-left"
    assert bbox.left == 40
    assert bbox.right == 200
    assert bbox.top == page_height - 700
    assert bbox.bottom == page_height - 650
    assert bbox.bottom > bbox.top


def test_item_text_prefers_visible_text() -> None:
    class Item:
        text = " extracted "
        orig = "ignored"

    assert item_text(Item()) == " extracted "
