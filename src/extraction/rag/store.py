from __future__ import annotations

import uuid
from typing import Protocol

from urllib.parse import urlparse, urlunparse

from extraction.errors import ExtractionError
from extraction.rag.models import ChildChunk, ChildHit
from extraction.settings import Settings

POINT_NAMESPACE = uuid.UUID("8c4b1424-46bf-46b6-8dc0-7f0268d891cd")


def normalize_qdrant_url(url: str) -> str:
    raw = url.strip().rstrip("/")
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.hostname or ""
    if not host:
        raise ExtractionError("QDRANT_NOT_CONFIGURED", "QDRANT_URL is missing a hostname.")
    port = parsed.port
    if host.endswith("cloud.qdrant.io") and port in {None, 80, 443}:
        port = 6333
    elif port is None:
        port = 443 if (parsed.scheme or "https") == "https" else 80
    return urlunparse((parsed.scheme or "https", f"{host}:{port}", parsed.path or "", "", "", ""))


def _qdrant_error(exc: Exception) -> ExtractionError:
    message = str(exc)
    if "name resolution" in message.lower() or "nodename nor servname" in message.lower() or "name or service not known" in message.lower():
        return ExtractionError(
            "QDRANT_UNAVAILABLE",
            "Cannot resolve Qdrant Cloud hostname. Use the exact dashboard URL with port 6333, e.g. https://<cluster-id>.<region>.aws.cloud.qdrant.io:6333.",
        )
    return ExtractionError("QDRANT_UNAVAILABLE", f"Cannot reach Qdrant Cloud: {exc}")


def point_id_for(child_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, child_id))


def _payload(child: ChildChunk, job_id: str) -> dict:
    return {
        "document_id": child.document_id,
        "job_id": job_id,
        "filename": child.filename,
        "media_type": child.media_type,
        "child_id": child.child_id,
        "parent_id": child.parent_id,
        "parent_type": child.parent_type,
        "parent_text": child.parent_text,
        "child_text": child.child_text,
        "element_type": child.element_type,
        "modality": child.modality,
        "unit_type": child.unit_type,
        "unit_index": child.unit_index,
        "element_ids": child.element_ids,
        "asset_path": child.asset_path,
        "t_start": child.t_start,
        "t_end": child.t_end,
    }


def _hit_from_payload(payload: dict, score: float) -> ChildHit:
    return ChildHit(
        child_id=payload["child_id"],
        parent_id=payload["parent_id"],
        parent_type=payload.get("parent_type", "unit"),
        parent_text=payload.get("parent_text", ""),
        child_text=payload.get("child_text", ""),
        score=score,
        filename=payload.get("filename", ""),
        unit_type=payload.get("unit_type", "file"),
        unit_index=int(payload.get("unit_index") or 0),
        element_type=payload.get("element_type", "paragraph"),
        modality=payload.get("modality", "text"),
        asset_path=payload.get("asset_path"),
        t_start=payload.get("t_start"),
        t_end=payload.get("t_end"),
        document_id=payload.get("document_id", ""),
    )


class ChunkStore(Protocol):
    def replace_document(
        self,
        document_id: str,
        job_id: str,
        children: list[ChildChunk],
        vectors: list[list[float]],
    ) -> int: ...

    def query(
        self,
        vector: list[float],
        limit: int,
        document_id: str | None = None,
    ) -> list[ChildHit]: ...


class MemoryChunkStore:
    _stores: dict[str, "MemoryChunkStore"] = {}

    def __init__(self) -> None:
        self.points: list[tuple[str, list[float], dict]] = []

    @classmethod
    def get(cls, collection: str) -> "MemoryChunkStore":
        store = cls._stores.get(collection)
        if store is None:
            store = cls()
            cls._stores[collection] = store
        return store

    @classmethod
    def reset(cls) -> None:
        cls._stores.clear()

    def replace_document(
        self,
        document_id: str,
        job_id: str,
        children: list[ChildChunk],
        vectors: list[list[float]],
    ) -> int:
        self.points = [point for point in self.points if point[2].get("document_id") != document_id]
        for child, vector in zip(children, vectors):
            self.points.append((point_id_for(child.child_id), vector, _payload(child, job_id)))
        return len(children)

    def query(
        self,
        vector: list[float],
        limit: int,
        document_id: str | None = None,
    ) -> list[ChildHit]:
        scored: list[ChildHit] = []
        for _point_id, stored, payload in self.points:
            if document_id and payload.get("document_id") != document_id:
                continue
            score = sum(left * right for left, right in zip(vector, stored))
            scored.append(_hit_from_payload(payload, float(score)))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:limit]


class QdrantChunkStore:
    def __init__(self, settings: Settings) -> None:
        if not settings.qdrant_url.strip():
            raise ExtractionError("QDRANT_NOT_CONFIGURED", "QDRANT_URL is not set.")
        from qdrant_client import QdrantClient, models

        self._models = models
        self.collection = settings.qdrant_collection
        self.dims = settings.euri_embedding_dims
        try:
            self.client = QdrantClient(
                url=normalize_qdrant_url(settings.qdrant_url),
                api_key=settings.qdrant_api_key or None,
                timeout=30,
            )
            self._ensure_collection()
        except ExtractionError:
            raise
        except Exception as exc:
            raise _qdrant_error(exc) from exc

    def _ensure_collection(self) -> None:
        models = self._models
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=self.dims, distance=models.Distance.COSINE),
            )
        for field in ("document_id", "parent_id"):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                continue

    def replace_document(
        self,
        document_id: str,
        job_id: str,
        children: list[ChildChunk],
        vectors: list[list[float]],
    ) -> int:
        models = self._models
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
                    )
                ),
            )
            points = [
                models.PointStruct(
                    id=point_id_for(child.child_id),
                    vector=vector,
                    payload=_payload(child, job_id),
                )
                for child, vector in zip(children, vectors)
            ]
            for start in range(0, len(points), 64):
                self.client.upsert(collection_name=self.collection, points=points[start : start + 64])
        except Exception as exc:
            raise _qdrant_error(exc) from exc
        return len(children)

    def query(
        self,
        vector: list[float],
        limit: int,
        document_id: str | None = None,
    ) -> list[ChildHit]:
        models = self._models
        query_filter = None
        if document_id:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
            )
        try:
            result = self.client.query_points(
                collection_name=self.collection,
                query=vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )
        except Exception as exc:
            raise _qdrant_error(exc) from exc
        hits = []
        for point in result.points:
            payload = dict(point.payload or {})
            hits.append(_hit_from_payload(payload, float(point.score or 0.0)))
        return hits


def get_chunk_store(settings: Settings) -> ChunkStore:
    url = (settings.qdrant_url or "").strip()
    if url.startswith("memory:"):
        return MemoryChunkStore.get(settings.qdrant_collection)
    return QdrantChunkStore(settings)
