from __future__ import annotations

from pathlib import Path

from app.models.common import RegionType
from app.models.document import CanonicalDocument


def write_document_markdown(path: Path, document: CanonicalDocument) -> Path:
    lines: list[str] = []
    meta = document.document
    lines.append(f"# {meta.get('filename') or meta.get('id')}")
    lines.append("")
    lines.append(f"- Document ID: `{meta.get('id')}`")
    lines.append(f"- Pages: {meta.get('page_count')}")
    lines.append(f"- Kind: {meta.get('kind')}")
    if document.warnings:
        lines.append(f"- Warnings: {', '.join(document.warnings)}")
    lines.append("")
    for page in document.pages:
        lines.append(f"## Page {page.page_number}")
        lines.append("")
        if page.image_path:
            lines.append(f"![Page {page.page_number}]({page.image_path})")
            lines.append("")
        for region in page.regions:
            element = region.element
            content = element.content if element else {}
            text = str(content.get("text") or region.extra.get("text") or "").strip()
            if region.type == RegionType.HEADING and text:
                lines.append(f"### {text}")
                lines.append("")
                continue
            if region.type in {RegionType.PARAGRAPH, RegionType.LIST, RegionType.FOOTNOTE, RegionType.CAPTION}:
                if text:
                    prefix = "- " if region.type == RegionType.LIST else ""
                    lines.append(f"{prefix}{text}")
                    lines.append("")
                continue
            if region.type in {RegionType.TABLE, RegionType.COMPLEX_TABLE}:
                table = content.get("table") or {}
                caption = table.get("caption")
                if caption:
                    lines.append(f"*{caption}*")
                    lines.append("")
                headers = table.get("headers") or []
                rows = table.get("rows") or []
                if headers:
                    lines.append("| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in rows:
                        padded = list(row) + [""] * (len(headers) - len(row))
                        lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
                    lines.append("")
                elif text:
                    lines.append(text)
                    lines.append("")
                continue
            figure = content.get("figure") or {}
            image_path = figure.get("original_asset") or figure.get("crop_asset")
            if image_path:
                lines.append(f"![{region.type.value}]({image_path})")
                lines.append("")
            if content.get("chart"):
                chart = content["chart"]
                if chart.get("title"):
                    lines.append(f"**Chart:** {chart['title']}")
                    lines.append("")
                if chart.get("visible_values"):
                    lines.append("Visible values: " + ", ".join(map(str, chart["visible_values"])))
                    lines.append("")
            if content.get("diagram"):
                diagram = content["diagram"]
                nodes = diagram.get("nodes") or []
                if nodes:
                    lines.append("Diagram nodes: " + ", ".join(n.get("label") or n.get("id") for n in nodes))
                    lines.append("")
            if text:
                lines.append(text)
                lines.append("")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path
