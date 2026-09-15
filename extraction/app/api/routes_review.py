from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import get_repo, storage
from app.core.exceptions import NotFoundError
from app.models.common import ValidationStatus

router = APIRouter()


class ReviewDecision(BaseModel):
    value: str | None = None
    status: str = "REVIEWED"
    notes: str | None = None


@router.post("/review-items/{review_id}")
def submit_review(review_id: str, decision: ReviewDecision):
    repo = get_repo()
    try:
        item = repo.resolve_review_item(review_id, decision.model_dump())
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    paths = storage().document_paths(item.document_id)
    if paths.document_json.exists() and decision.value is not None:
        payload = json.loads(paths.document_json.read_text(encoding="utf-8"))
        for page in payload.get("pages", []):
            for region in page.get("regions", []):
                if region.get("id") != item.region_id:
                    continue
                element = region.get("element") or {}
                content = element.get("content") or {}
                content["text"] = decision.value
                element["content"] = content
                validation = element.get("validation") or {}
                validation["status"] = ValidationStatus.REVIEWED.value
                validation["needs_review"] = False
                validation["reasons"] = ["human_reviewed"]
                element["validation"] = validation
                region["element"] = element
        paths.document_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return item.model_dump()
