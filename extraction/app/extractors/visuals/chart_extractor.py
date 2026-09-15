from __future__ import annotations

from pathlib import Path

from app.extractors.text.ocr import ocr_image
from app.extractors.vlm.client import VLMClient
from app.extractors.vlm.prompts import CHART_PROMPT
from app.models.figure import ChartModel, ChartSeries


def extract_chart(
    crop_path: Path,
    vlm: VLMClient | None = None,
) -> tuple[ChartModel, dict]:
    ocr = None
    try:
        ocr = ocr_image(crop_path)
        ocr_text = ocr.text
        ocr_conf = ocr.average_confidence
    except Exception:
        ocr_text = ""
        ocr_conf = None

    chart = ChartModel(visible_values=[], caption=None)
    vlm_payload = None
    if vlm is not None:
        vlm_payload = vlm.analyze_image(crop_path, CHART_PROMPT)
        if vlm_payload:
            chart = ChartModel(
                title=vlm_payload.get("title"),
                x_axis=vlm_payload.get("x_axis"),
                y_axis=vlm_payload.get("y_axis"),
                units=vlm_payload.get("units"),
                legend=vlm_payload.get("legend") or [],
                series=[
                    ChartSeries(name=item.get("name", ""), values=item.get("values") or [])
                    for item in (vlm_payload.get("series") or [])
                    if isinstance(item, dict)
                ],
                data_labels=vlm_payload.get("data_labels") or [],
                trend=vlm_payload.get("trend"),
                caption=vlm_payload.get("caption"),
                visible_values=vlm_payload.get("visible_values") or [],
            )
    if ocr_text and not chart.visible_values:
        chart.visible_values = [line for line in ocr_text.splitlines() if line.strip()]
    evidence = {
        "ocr_text": ocr_text,
        "ocr_confidence": ocr_conf,
        "vlm": vlm_payload,
    }
    return chart, evidence
