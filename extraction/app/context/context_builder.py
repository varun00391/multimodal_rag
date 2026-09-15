from __future__ import annotations

from app.context.reading_order import assign_reading_order
from app.context.relationships import build_relationships
from app.models.document import CanonicalDocument, DocumentProfile, Relationship
from app.models.page import PageModel
from app.models.region import Region


def build_canonical_document(
    *,
    document_id: str,
    filename: str,
    profile: DocumentProfile,
    pages: list[PageModel],
    assets: list,
    warnings: list[str],
) -> CanonicalDocument:
    all_regions: list[Region] = []
    for page in pages:
        assign_reading_order(page.regions, page.width_px or page.width)
        all_regions.extend(page.regions)
        page.regions.sort(key=lambda r: r.extra.get("reading_order") or 10**6)
    relationships: list[Relationship] = build_relationships(all_regions)
    return CanonicalDocument(
        document={
            "id": document_id,
            "filename": filename,
            "page_count": profile.page_count,
            "sha256": None,
            "kind": (
                "scanned"
                if profile.is_probably_scanned
                else "hybrid"
                if profile.is_hybrid
                else "born_digital"
            ),
        },
        pages=pages,
        relationships=relationships,
        assets=assets,
        warnings=warnings,
        profile=profile,
    )
