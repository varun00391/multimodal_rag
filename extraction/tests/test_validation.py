from app.models.common import ConfidenceBand
from app.validation.confidence import band_for, score_confidence
from app.validation.reconciliation import reconcile_text_values


def test_reconcile_agrees_when_sources_match():
    result = reconcile_text_values(
        [
            {"value": "INV-1023", "source": "pymupdf"},
            {"value": "INV-1023", "source": "ocr"},
            {"value": "INV-1023", "source": "vlm"},
        ]
    )
    assert result["status"] == "AGREED"
    assert result["value"] == "INV-1023"
    assert set(result["sources"]) == {"pymupdf", "ocr", "vlm"}


def test_reconcile_keeps_conflict_candidates():
    result = reconcile_text_values(
        [
            {"value": "INV-1023", "source": "pymupdf"},
            {"value": "INV-1033", "source": "ocr"},
            {"value": "INV-1023", "source": "vlm"},
        ]
    )
    assert result["status"] == "CONFLICT"
    assert len(result["candidates"]) == 2
    values = {item["value"] for item in result["candidates"]}
    assert values == {"INV-1023", "INV-1033"}


def test_confidence_bands():
    assert band_for(0.95) == ConfidenceBand.HIGH
    assert band_for(0.8) == ConfidenceBand.MEDIUM
    assert band_for(0.2) == ConfidenceBand.LOW
    assert 0 <= score_confidence(source_agreement=1, extraction_quality=1) <= 1
