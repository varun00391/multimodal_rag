from app.context.reading_order import assign_reading_order
from app.models.common import RegionType
from app.models.page import PageProfile
from app.models.region import Region
from app.orchestration.router import route_region


def _region(region_id: str, region_type: RegionType, bbox: list[float]) -> Region:
    return Region(id=region_id, type=region_type, page=1, bbox=bbox, bbox_pdf=bbox)


def test_router_text_uses_native_then_ocr_fallback():
    region = _region("r1", RegionType.PARAGRAPH, [0, 0, 10, 10])
    engines = route_region(region, None)
    assert engines[0] == "native_text"
    assert "ocr_fallback" in engines


def test_router_table_uses_table_engine():
    region = _region("r2", RegionType.TABLE, [0, 0, 10, 10])
    profile = PageProfile(page_number=1, width=100, height=100)
    engines = route_region(region, profile)
    assert "table_engine" in engines


def test_reading_order_left_column_before_right():
    left_top = _region("l1", RegionType.PARAGRAPH, [10, 10, 80, 40])
    left_bottom = _region("l2", RegionType.PARAGRAPH, [10, 50, 80, 80])
    right_top = _region("r1", RegionType.PARAGRAPH, [120, 10, 190, 40])
    right_bottom = _region("r2", RegionType.PARAGRAPH, [120, 50, 190, 80])
    ordered = assign_reading_order([right_top, left_bottom, right_bottom, left_top], page_width=200)
    ids = [region.id for region in sorted(ordered, key=lambda r: r.extra["reading_order"])]
    assert ids == ["l1", "l2", "r1", "r2"]
