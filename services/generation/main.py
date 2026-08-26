from __future__ import annotations

from fastapi import APIRouter, Depends

from rag_shared.app_factory import create_service_app, verify_internal_token
from rag_shared.config import get_settings
from rag_shared.rag_env import ensure_rag_env
from rag_shared.schemas.internal import GenerationRequest, GenerationResponse, RetrievalHitPayload
from rag_shared.services.rag_settings import to_rag_settings

from rag.generate import generate_answer
from rag.retrieve import RetrievalHit

internal = APIRouter(tags=["internal"], dependencies=[Depends(verify_internal_token)])


def _payload_to_hit(payload: RetrievalHitPayload) -> RetrievalHit:
    return RetrievalHit(
        child=payload.child,
        parent=payload.parent,
        fusion_score=payload.fusion_score,
        dense_rank=payload.dense_rank,
        lexical_rank=payload.lexical_rank,
    )


@internal.post("/generation/answer", response_model=GenerationResponse)
def generate_answer_endpoint(payload: GenerationRequest) -> GenerationResponse:
    settings = get_settings()
    ensure_rag_env(settings)
    rag_settings = to_rag_settings(settings)
    hits = [_payload_to_hit(item) for item in payload.hits]
    result = generate_answer(payload.query, hits, rag_settings, style=payload.style)
    return GenerationResponse(answer=result.text, model=rag_settings.vision_model)


app = create_service_app(service_name="generation", internal_routers=[internal])
