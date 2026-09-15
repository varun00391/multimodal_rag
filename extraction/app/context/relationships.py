from __future__ import annotations

from app.models.common import RegionType, bbox_from_seq
from app.models.document import Relationship
from app.models.region import Region
from app.validation.consistency import caption_near_visual, figure_references


def build_relationships(regions: list[Region]) -> list[Relationship]:
    relationships: list[Relationship] = []
    by_id = {region.id: region for region in regions}
    captions = [r for r in regions if r.type == RegionType.CAPTION]
    visuals = [
        r
        for r in regions
        if r.type
        in {
            RegionType.FIGURE,
            RegionType.IMAGE,
            RegionType.CHART,
            RegionType.DIAGRAM,
            RegionType.TABLE,
        }
    ]
    footnotes = [r for r in regions if r.type == RegionType.FOOTNOTE]
    texts = [
        r
        for r in regions
        if r.type in {RegionType.PARAGRAPH, RegionType.HEADING, RegionType.LIST}
    ]

    for region in regions:
        if region.parent_id and region.parent_id in by_id:
            rel_type = "has_caption" if region.type == RegionType.CAPTION else "contains"
            relationships.append(
                Relationship(source_id=region.parent_id, target_id=region.id, type=rel_type)
            )

    for caption in captions:
        if caption.parent_id:
            continue
        for visual in visuals:
            if caption_near_visual(caption, visual):
                relationships.append(
                    Relationship(source_id=visual.id, target_id=caption.id, type="has_caption")
                )
                caption.parent_id = visual.id
                break

    for table in [r for r in regions if r.type in {RegionType.TABLE, RegionType.COMPLEX_TABLE}]:
        for footnote in footnotes:
            if footnote.page == table.page and bbox_from_seq(footnote.bbox).y0 >= bbox_from_seq(table.bbox).y1 - 20:
                relationships.append(
                    Relationship(source_id=table.id, target_id=footnote.id, type="has_footnote")
                )

    visual_labels = {}
    for visual in visuals + captions:
        text = ""
        if visual.element:
            text = str(visual.element.content.get("text") or visual.element.content.get("caption") or "")
        elif visual.extra.get("text"):
            text = str(visual.extra["text"])
        for ref in figure_references(text):
            visual_labels[ref] = visual.id

    for text_region in texts:
        blob = ""
        if text_region.element:
            blob = str(text_region.element.content.get("text") or "")
        elif text_region.extra.get("text"):
            blob = str(text_region.extra["text"])
        for ref in figure_references(blob):
            target = visual_labels.get(ref)
            if not target:
                continue
            rel = "explains" if "table" in ref else "references"
            relationships.append(
                Relationship(source_id=text_region.id, target_id=target, type=rel)
            )
    return relationships
