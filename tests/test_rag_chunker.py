from __future__ import annotations

from extraction.canonicalize import build_document
from extraction.elements import picture_element, table_element, text_element
from extraction.models.cdr import Unit
from extraction.rag.chunker import chunk_document, table_to_markdown
from extraction.rag.models import ChildHit
from extraction.rag.retrieve import expand_parents


def _document(settings, units):
    del settings
    return build_document(
        document_id="doc-1",
        filename="policy.pdf",
        media_type="application/pdf",
        sha256="doc-1",
        size_bytes=12,
        stored_path="original/policy.pdf",
        units=units,
        diagnostics=[],
    )


def test_packs_prose_under_one_unit_parent(settings) -> None:
    units = [
        Unit(
            unit_type="page",
            index=1,
            primary_route="pymupdf",
            elements=[
                text_element(
                    unit_type="page",
                    unit_index=1,
                    order=1,
                    text="Leave policy covers vacation.",
                    extractor="pymupdf",
                    version="1.0",
                ),
                text_element(
                    unit_type="page",
                    unit_index=1,
                    order=2,
                    text="Employees receive twenty days of leave.",
                    extractor="pymupdf",
                    version="1.0",
                ),
            ],
        )
    ]
    children = chunk_document(_document(settings, units), settings)
    assert len(children) == 1
    child = children[0]
    assert child.parent_type == "unit"
    assert child.parent_id.endswith(":unit:page:1")
    assert "vacation" in child.child_text
    assert "twenty days" in child.child_text
    assert child.parent_text == child.child_text or "vacation" in child.parent_text
    assert child.embed_text.startswith("policy.pdf | page 1")


def test_large_table_uses_table_parent(settings) -> None:
    rows = [[f"city-{index}", f"country-{index}"] for index in range(80)]
    table = table_element(
        unit_type="sheet",
        unit_index=1,
        order=1,
        columns=["city", "country"],
        rows=rows,
        extractor="pandas",
        version="1.0",
    )
    units = [Unit(unit_type="sheet", index=1, primary_route="pandas", elements=[table])]
    document = _document(settings, units)
    markdown = table_to_markdown(table.table)
    assert len(markdown) > settings.rag_chunk_chars
    children = chunk_document(document, settings)
    assert len(children) > 1
    assert all(child.parent_type == "table" for child in children)
    assert all(child.parent_id.endswith(f":table:{table.element_id}") for child in children)
    assert children[0].parent_text == markdown
    assert "city" in children[0].child_text


def test_picture_child_keeps_asset(settings) -> None:
    picture = picture_element(
        unit_type="page",
        unit_index=2,
        order=1,
        asset_path="page-2-image-1.png",
        extractor="pymupdf",
        version="1.0",
        text="Bar chart of headcount by office.",
    )
    units = [Unit(unit_type="page", index=2, primary_route="pymupdf", elements=[picture])]
    children = chunk_document(_document(settings, units), settings)
    assert len(children) == 1
    assert children[0].modality == "image"
    assert children[0].asset_path == "page-2-image-1.png"
    assert "headcount" in children[0].child_text


def test_expand_parents_dedupes_and_caps() -> None:
    hits = [
        ChildHit(
            child_id="c1",
            parent_id="p1",
            parent_type="unit",
            parent_text="page one",
            child_text="alpha",
            score=0.9,
            filename="a.pdf",
            unit_type="page",
            unit_index=1,
            element_type="paragraph",
            modality="text",
            document_id="d",
        ),
        ChildHit(
            child_id="c2",
            parent_id="p1",
            parent_type="unit",
            parent_text="page one",
            child_text="beta",
            score=0.8,
            filename="a.pdf",
            unit_type="page",
            unit_index=1,
            element_type="paragraph",
            modality="text",
            document_id="d",
        ),
        ChildHit(
            child_id="c3",
            parent_id="p2",
            parent_type="unit",
            parent_text="page two",
            child_text="gamma",
            score=0.7,
            filename="a.pdf",
            unit_type="page",
            unit_index=2,
            element_type="paragraph",
            modality="text",
            document_id="d",
        ),
        ChildHit(
            child_id="c4",
            parent_id="p3",
            parent_type="unit",
            parent_text="page three",
            child_text="delta",
            score=0.6,
            filename="a.pdf",
            unit_type="page",
            unit_index=3,
            element_type="paragraph",
            modality="text",
            document_id="d",
        ),
    ]
    parents = expand_parents(hits, parent_limit=2)
    assert [parent.parent_id for parent in parents] == ["p1", "p2"]
    assert [child.child_id for child in parents[0].children] == ["c1", "c2"]


def test_normalize_qdrant_cloud_url_adds_port() -> None:
    from extraction.rag.store import normalize_qdrant_url

    url = normalize_qdrant_url(
        "https://07000f97-52e7-45d6-a997-d651f45fe52d.ca-central-1-0.aws.cloud.qdrant.io"
    )
    assert url.endswith(":6333")
    same = normalize_qdrant_url(url)
    assert same == url


def _hit(child_id: str, parent_id: str, score: float, **kwargs) -> ChildHit:
    payload = dict(
        child_id=child_id,
        parent_id=parent_id,
        parent_type="unit",
        parent_text="page",
        child_text=child_id,
        score=score,
        filename="a.pdf",
        unit_type="page",
        unit_index=1,
        element_type="paragraph",
        modality="text",
        document_id="d",
    )
    payload.update(kwargs)
    return ChildHit(**payload)


def test_fuse_rrf_ranks_overlap_first() -> None:
    from extraction.rag.retrieve import fuse_rrf

    dense = [_hit("c1", "p1", 0.9), _hit("c2", "p2", 0.8)]
    sparse = [_hit("c2", "p2", 4.0), _hit("c3", "p3", 3.0)]
    fused = fuse_rrf(dense, sparse, rrf_k=60, limit=8)
    assert fused[0].child_id == "c2"
    assert fused[0].bm25_hit is True
    assert fused[0].dense_score == 0.8


def test_dense_cutoff_drops_weak_dense_keeps_bm25() -> None:
    from extraction.rag.retrieve import apply_dense_cutoff

    hits = [
        _hit("weak", "p1", 0.2, dense_score=0.2, bm25_hit=False),
        _hit("strong", "p2", 0.81, dense_score=0.81, bm25_hit=False),
        _hit("lexical", "p3", 0.05, dense_score=0.12, bm25_hit=True),
    ]
    kept = apply_dense_cutoff(hits, 0.40)
    assert [hit.child_id for hit in kept] == ["strong", "lexical"]
