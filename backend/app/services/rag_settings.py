from __future__ import annotations

from rag.config import Settings as RagSettings

from app.config import Settings
from app.services.rag_runtime import normalize_qdrant_url


def to_rag_settings(app_settings: Settings) -> RagSettings:
    return RagSettings(
        groq_api_key=app_settings.groq_api_key,
        groq_base_url=app_settings.groq_base_url.rstrip("/"),
        vision_model=app_settings.groq_vision_model,
        euri_api_key=app_settings.euri_api_key,
        euri_base_url=app_settings.euri_base_url.rstrip("/"),
        embedding_model=app_settings.euri_embedding_model,
        embedding_dimensions=app_settings.euri_embedding_dimensions,
        qdrant_url=normalize_qdrant_url(app_settings.qdrant_url),
        qdrant_api_key=app_settings.qdrant_api_key.strip(),
        qdrant_collection=app_settings.qdrant_collection.strip(),
    )
