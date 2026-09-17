from __future__ import annotations

from extraction.rag.models import ChildHit, RetrievedParent


def fuse_rrf(
    dense_hits: list[ChildHit],
    sparse_hits: list[ChildHit],
    rrf_k: int,
    limit: int,
) -> list[ChildHit]:
    dense_rank = {hit.child_id: index for index, hit in enumerate(dense_hits, start=1)}
    sparse_rank = {hit.child_id: index for index, hit in enumerate(sparse_hits, start=1)}
    dense_by_id = {hit.child_id: hit for hit in dense_hits}
    sparse_by_id = {hit.child_id: hit for hit in sparse_hits}
    fused: list[ChildHit] = []
    seen: set[str] = set()
    for child_id in list(dense_rank) + list(sparse_rank):
        if child_id in seen:
            continue
        seen.add(child_id)
        rrf = 0.0
        if child_id in dense_rank:
            rrf += 1.0 / (rrf_k + dense_rank[child_id])
        if child_id in sparse_rank:
            rrf += 1.0 / (rrf_k + sparse_rank[child_id])
        base = dense_by_id.get(child_id) or sparse_by_id[child_id]
        fused.append(
            base.model_copy(
                update={
                    "score": rrf,
                    "dense_score": dense_by_id[child_id].score if child_id in dense_by_id else None,
                    "bm25_hit": child_id in sparse_rank,
                }
            )
        )
    fused.sort(key=lambda hit: hit.score, reverse=True)
    return fused[:limit]


def apply_dense_cutoff(hits: list[ChildHit], cutoff: float) -> list[ChildHit]:
    if cutoff <= 0:
        return hits
    kept: list[ChildHit] = []
    for hit in hits:
        if hit.bm25_hit:
            kept.append(hit)
            continue
        dense = hit.dense_score if hit.dense_score is not None else hit.score
        if dense >= cutoff:
            kept.append(hit)
    return kept


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
