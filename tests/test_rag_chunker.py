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
