from __future__ import annotations

from pathlib import Path

from app.extractors.text.ocr import ocr_image
from app.extractors.vlm.client import VLMClient
from app.extractors.vlm.prompts import DIAGRAM_PROMPT
from app.models.figure import DiagramEdge, DiagramModel, DiagramNode


def extract_diagram(
    crop_path: Path,
    vlm: VLMClient | None = None,
    vector_count: int = 0,
) -> tuple[DiagramModel, dict]:
    ocr_text = ""
    try:
        ocr = ocr_image(crop_path)
        ocr_text = ocr.text
    except Exception:
        ocr = None
    diagram = DiagramModel()
    vlm_payload = None
    if vlm is not None:
        vlm_payload = vlm.analyze_image(crop_path, DIAGRAM_PROMPT)
        if vlm_payload:
            nodes = []
            for item in vlm_payload.get("nodes") or []:
                if not isinstance(item, dict):
                    continue
                nodes.append(
                    DiagramNode(
                        id=str(item.get("id") or item.get("label") or f"n{len(nodes)+1}"),
                        label=str(item.get("label") or ""),
                    )
                )
            edges = []
            for item in vlm_payload.get("edges") or []:
                if not isinstance(item, dict):
                    continue
                source = item.get("from") or item.get("source")
                target = item.get("to") or item.get("target")
                if source and target:
                    edges.append(
                        DiagramEdge(
                            source=str(source),
                            target=str(target),
                            label=str(item.get("label") or ""),
                        )
                    )
            diagram = DiagramModel(
                nodes=nodes,
                edges=edges,
                groups=vlm_payload.get("groups") or [],
                caption=vlm_payload.get("caption"),
            )
    if not diagram.nodes and ocr_text:
        labels = [line.strip() for line in ocr_text.splitlines() if line.strip()]
        diagram.nodes = [
            DiagramNode(id=f"n{i+1}", label=label) for i, label in enumerate(labels[:40])
        ]
    evidence = {
        "ocr_text": ocr_text,
        "vlm": vlm_payload,
        "vector_count": vector_count,
        "ocr_confidence": getattr(ocr, "average_confidence", None),
    }
    return diagram, evidence
