from __future__ import annotations

from extraction.rag.models import ChildHit, RetrievedParent


def expand_parents(hits: list[ChildHit], parent_limit: int) -> list[RetrievedParent]:
    parents: list[RetrievedParent] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.parent_id in seen:
            existing = next(item for item in parents if item.parent_id == hit.parent_id)
            existing.children.append(hit)
            continue
        if len(parents) >= parent_limit:
            continue
        seen.add(hit.parent_id)
        parents.append(
            RetrievedParent(
                parent_id=hit.parent_id,
                parent_type=hit.parent_type,
                parent_text=hit.parent_text,
                filename=hit.filename,
                unit_type=hit.unit_type,
                unit_index=hit.unit_index,
                score=hit.score,
                children=[hit],
            )
        )
    return parents
