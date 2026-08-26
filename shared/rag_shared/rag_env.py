from __future__ import annotations

import os

from rag_shared.config import Settings
from rag_shared.services.rag_runtime import normalize_qdrant_url


def ensure_rag_env(settings: Settings) -> None:
    """Mirror FastAPI settings into os.environ for rag.config.Settings.from_env()."""
    env_map = {
        "GROQ_API_KEY": settings.groq_api_key,
        "GROQ_BASE_URL": settings.groq_base_url,
        "GROQ_VISION_MODEL": settings.groq_vision_model,
        "EURI_API_KEY": settings.euri_api_key,
        "EURI_BASE_URL": settings.euri_base_url,
        "EURI_EMBEDDING_MODEL": settings.euri_embedding_model,
        "EURI_EMBEDDING_DIMENSIONS": str(settings.euri_embedding_dimensions),
        "QDRANT_URL": normalize_qdrant_url(settings.qdrant_url),
        "QDRANT_API_KEY": settings.qdrant_api_key,
        "QDRANT_COLLECTION": settings.qdrant_collection,
    }
    for key, value in env_map.items():
        if value:
            os.environ[key] = value
