from __future__ import annotations

import math
from pathlib import Path

from extraction.clients.euron import get_euron_client
from extraction.errors import ExtractionError
from extraction.rag.models import ChildChunk
from extraction.settings import Settings

BATCH_SIZE = 32


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def _raise_embed_error(exc: Exception) -> None:
    from openai import APIStatusError, AuthenticationError

    if isinstance(exc, AuthenticationError):
        raise ExtractionError(
            "EMBEDDINGS_UNAUTHORIZED",
            "Euron rejected EURI_API_KEY as invalid or inactive. Create a new key at euron.one and restart the container.",
        ) from exc
    if isinstance(exc, APIStatusError):
        raise ExtractionError(
            "EMBEDDINGS_FAILED",
            f"Euron embeddings returned HTTP {exc.status_code}.",
        ) from exc
    raise ExtractionError("EMBEDDINGS_FAILED", "Euron embeddings request failed.") from exc


def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = get_euron_client(settings)
    if client is None:
        raise ExtractionError("EMBEDDINGS_UNAVAILABLE", "EURI_API_KEY is not set.")
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        try:
            response = client.embeddings.create(
                model=settings.euri_embedding_model,
                input=batch,
                dimensions=settings.euri_embedding_dims,
            )
        except Exception as exc:
            _raise_embed_error(exc)
            raise
        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(batch):
            raise ExtractionError("EMBEDDINGS_FAILED", "Embedding API returned a partial batch.")
        for item in ordered:
            vectors.append(l2_normalize(list(item.embedding)))
    return vectors


def embed_children(settings: Settings, children: list[ChildChunk], assets_dir: Path) -> list[list[float]]:
    del assets_dir
    return embed_texts(settings, [child.embed_text for child in children])
