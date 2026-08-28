from pathlib import Path

from app.config import Settings
from app.models.canonical import (
    BoundingBox,
    CanonicalElement,
    CanonicalPage,
    ElementType,
)
from app.models.inspection import LayoutSignals, PageInspection, TextSignals
from app.validation.layout import validate_layout
from app.validation.tables import validate_tables
from app.validation.text import repeated_symbol_ratio, validate_text
from app.validation.validator import PageValidator
from app.validation.visuals import validate_visuals


def _page(*elements: CanonicalElement, width: float = 612, height: float = 792) -> CanonicalPage:
    return CanonicalPage(page=1, width=width, height=height, elements=list(elements), primary_route="pymupdf")


def _element(
    element_id: str,
    element_type: ElementType,
    *,
    text: str | None = None,
    markdown: str | None = None,
    html: str | None = None,
    bbox: BoundingBox | None = None,
    asset: str | None = None,
    reading_order: int = 1,
    confidence: float = 0.9,
) -> CanonicalElement:
    return CanonicalElement(
        element_id=element_id,
        type=element_type,
        page=1,
        reading_order=reading_order,
        text=text,
        markdown=markdown,
        html=html,
        bbox=bbox,
        asset=asset,
        confidence=confidence,
    )


def test_repeated_symbol_ratio_detects_garbage() -> None:
    assert repeated_symbol_ratio("........") > 0.9
    assert repeated_symbol_ratio("Normal sentence with variety.") < 0.3


def test_text_validator_flags_corrupt_native_text() -> None:
    inspection = PageInspection(
        page=1,
        width=612,
        height=792,
        text=TextSignals(character_count=200),
    )
    page = _page(
        _element(
            "e1",
            ElementType.PARAGRAPH,
            text="\ufffd" * 80 + " few words",
            bbox=BoundingBox(left=72, top=72, right=200, bottom=100),
        )
    )
    codes = {item.code for item in validate_text(page, inspection)}
    assert "NATIVE_TEXT_CORRUPT" in codes


def test_text_validator_skips_unextracted_scans() -> None:
    from app.models.canonical import ExtractionError

    page = _page()
    page.errors.append(
        ExtractionError(code="SCANNED_PAGE_NOT_EXTRACTED", message="skip", page=1)
    )
    inspection = PageInspection(page=1, width=612, height=792, probable_scan=True)
    assert validate_text(page, inspection) == []


def test_layout_validator_flags_out_of_bounds_and_duplicate_order() -> None:
    page = _page(
        _element(
            "e1",
            ElementType.PARAGRAPH,
            text="One",
            bbox=BoundingBox(left=0, top=0, right=700, bottom=40),
            reading_order=1,
        ),
        _element(
            "e2",
            ElementType.PARAGRAPH,
            text="Two",
            bbox=BoundingBox(left=10, top=50, right=100, bottom=80),
            reading_order=1,
        ),
    )
    codes = {item.code for item in validate_layout(page)}
    assert "BBOX_OUT_OF_BOUNDS" in codes
    assert "READING_ORDER_INVALID" in codes


def test_table_validator_flags_inconsistent_markdown() -> None:
    page = _page(
        _element(
            "t1",
            ElementType.TABLE,
            text="A B",
            markdown="| A | B |\n| --- | --- |\n| 1 | 2 | 3 |",
            bbox=BoundingBox(left=40, top=80, right=500, bottom=200),
        )
    )
    codes = {item.code for item in validate_tables(page, None)}
    assert "TABLE_STRUCTURE_INVALID" in codes


def test_table_validator_accepts_consistent_markdown() -> None:
    page = _page(
        _element(
            "t1",
            ElementType.TABLE,
            text="Region Value",
            markdown="| Region | Value |\n| --- | --- |\n| North | 10 |",
            html="<table><tr><td>Region</td><td>Value</td></tr></table>",
            bbox=BoundingBox(left=40, top=80, right=500, bottom=200),
        )
    )
    assert validate_tables(page, None) == []


def test_visual_validator_flags_missing_crop(tmp_path: Path) -> None:
    page = _page(
        _element(
            "v1",
            ElementType.CHART,
            text=None,
            bbox=BoundingBox(left=50, top=400, right=300, bottom=600),
            asset="assets/charts/missing.png",
        )
    )
    inspection = PageInspection(
        page=1,
        width=612,
        height=792,
        layout=LayoutSignals(figure_candidate_count=3),
    )
    codes = {item.code for item in validate_visuals(page, inspection, workspace=tmp_path)}
    assert "VISUAL_CROP_MISSING" in codes
    assert "VISUAL_MEANING_MISSING" in codes


def test_page_validator_sets_confidence_and_machine_readable_errors() -> None:
    settings = Settings(
        extraction_output_dir=Path("/tmp/unused-output"),
        extraction_database_path=Path("/tmp/unused.db"),
    )
    validator = PageValidator(settings)
    page = _page(
        _element(
            "e1",
            ElementType.PARAGRAPH,
            text="Hello world",
            bbox=BoundingBox(left=72, top=72, right=200, bottom=96),
        )
    )
    page.routing_confidence = 0.9
    result = validator.apply(page, None)
    assert result.passed is True
    assert page.validation_confidence == 1.0
    assert page.overall_confidence == 0.9
    assert result.failures == []


def test_formula_missing_is_reported_when_inspection_expects_formulas() -> None:
    settings = Settings(
        extraction_output_dir=Path("/tmp/unused-output"),
        extraction_database_path=Path("/tmp/unused.db"),
    )
    page = _page(
        _element(
            "e1",
            ElementType.PARAGRAPH,
            text="See the expression above.",
            bbox=BoundingBox(left=72, top=72, right=300, bottom=96),
        )
    )
    inspection = PageInspection(
        page=1,
        width=612,
        height=792,
        layout=LayoutSignals(formula_like_regions=2),
    )
    result = PageValidator(settings).apply(page, inspection)
    assert any(item.code == "FORMULA_MISSING" for item in result.failures)
    assert result.passed is True
