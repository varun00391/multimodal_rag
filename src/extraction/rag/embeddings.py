from __future__ import annotations

import logging
import math
from pathlib import Path

from extraction.clients.euron import get_euron_client
from extraction.errors import ExtractionError
from extraction.rag.models import ChildChunk
from extraction.settings import Settings

LOGGER = logging.getLogger(__name__)
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


def _embed_image(settings: Settings, path: Path, caption: str) -> list[float] | None:
    import base64
    import mimetypes

    import httpx

    if not settings.euri_api_key or not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data_url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    url = settings.euri_base_url.rstrip("/") + "/embeddings"
    payload = {
        "model": settings.euri_embedding_model,
        "dimensions": settings.euri_embedding_dims,
        "input": [
            {"type": "text", "text": caption or path.name},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.euri_api_key}"},
            json=payload,
            timeout=60.0,
        )
        if response.status_code >= 400:
            LOGGER.info("Euron image embedding rejected (%s); using caption.", response.status_code)
            return None
        data = response.json()["data"]
        vector = list(sorted(data, key=lambda item: item.get("index", 0))[0]["embedding"])
        return l2_normalize(vector)
    except Exception:
        LOGGER.info("Euron image embedding failed; using caption.", exc_info=True)
        return None


def embed_children(settings: Settings, children: list[ChildChunk], assets_dir: Path) -> list[list[float]]:
    vectors: list[list[float]] = []
    text_indexes: list[int] = []
    text_payloads: list[str] = []
    for index, child in enumerate(children):
        if child.modality == "image" and child.asset_path:
            image_path = assets_dir / child.asset_path
            image_vector = _embed_image(settings, image_path, child.child_text)
            if image_vector is not None:
                vectors.append(image_vector)
                continue
        vectors.append([])
        text_indexes.append(index)
        text_payloads.append(child.embed_text)
    if text_payloads:
        text_vectors = embed_texts(settings, text_payloads)
        for index, vector in zip(text_indexes, text_vectors):
            vectors[index] = vector
    return vectors
