from __future__ import annotations

import logging
import uuid
from typing import Protocol
from urllib.parse import urlparse, urlunparse

from extraction.errors import ExtractionError
from extraction.rag.models import ChildChunk, ChildHit
from extraction.rag.retrieve import fuse_rrf
from extraction.rag.sparse import bm25_score, sparse_pairs, sparse_tf
from extraction.settings import Settings

LOGGER = logging.getLogger(__name__)
POINT_NAMESPACE = uuid.UUID("8c4b1424-46bf-46b6-8dc0-7f0268d891cd")
DENSE_NAME = "dense"
BM25_NAME = "bm25"


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
        dense_score=score,
        bm25_hit=False,
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
        query_text: str,
        limit: int,
        prefetch: int,
        rrf_k: int,
        document_id: str | None = None,
    ) -> list[ChildHit]: ...


class MemoryChunkStore:
    _stores: dict[str, "MemoryChunkStore"] = {}

    def __init__(self) -> None:
        self.points: list[tuple[str, list[float], dict[int, float], dict]] = []

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
        self.points = [point for point in self.points if point[3].get("document_id") != document_id]
        for child, vector in zip(children, vectors):
            self.points.append(
                (
                    point_id_for(child.child_id),
                    vector,
                    sparse_tf(child.embed_text),
                    _payload(child, job_id),
                )
            )
        return len(children)

    def query(
        self,
        vector: list[float],
        query_text: str,
        limit: int,
        prefetch: int,
        rrf_k: int,
        document_id: str | None = None,
    ) -> list[ChildHit]:
        candidates = [
            point for point in self.points if not document_id or point[3].get("document_id") == document_id
        ]
        dense_hits: list[ChildHit] = []
        for _point_id, stored, _sparse, payload in candidates:
            score = sum(left * right for left, right in zip(vector, stored))
            dense_hits.append(_hit_from_payload(payload, float(score)))
        dense_hits.sort(key=lambda hit: hit.score, reverse=True)
        dense_hits = dense_hits[:prefetch]

        query_tf = sparse_tf(query_text)
        sparse_hits: list[ChildHit] = []
        if query_tf and candidates:
            doc_count = len(candidates)
            df: dict[int, int] = {}
            lengths = []
            for _point_id, _stored, sparse, _payload in candidates:
                lengths.append(sum(sparse.values()) or 1.0)
                for term in sparse:
                    df[term] = df.get(term, 0) + 1
            avgdl = sum(lengths) / len(lengths)
            for _point_id, _stored, sparse, payload in candidates:
                score = bm25_score(query_tf, sparse, doc_count, df, avgdl)
                if score <= 0:
                    continue
                hit = _hit_from_payload(payload, float(score))
                hit.bm25_hit = True
                sparse_hits.append(hit)
            sparse_hits.sort(key=lambda hit: hit.score, reverse=True)
            sparse_hits = sparse_hits[:prefetch]

        if not sparse_hits:
            return dense_hits[:limit]
        return fuse_rrf(dense_hits, sparse_hits, rrf_k=rrf_k, limit=limit)


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

    def _schema_ok(self) -> bool:
        info = self.client.get_collection(self.collection)
        params = info.config.params
        vectors = params.vectors
        if not isinstance(vectors, dict) or DENSE_NAME not in vectors:
            return False
        sparse = params.sparse_vectors or {}
        return BM25_NAME in sparse

    def _ensure_collection(self) -> None:
        models = self._models
        if self.client.collection_exists(self.collection) and not self._schema_ok():
            LOGGER.warning("Recreating Qdrant collection %s for hybrid dense+BM25 schema.", self.collection)
            self.client.delete_collection(self.collection)
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config={
                    DENSE_NAME: models.VectorParams(size=self.dims, distance=models.Distance.COSINE),
                },
                sparse_vectors_config={
                    BM25_NAME: models.SparseVectorParams(modifier=models.Modifier.IDF),
                },
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
            points = []
            for child, vector in zip(children, vectors):
                named = {DENSE_NAME: vector}
                indices, values = sparse_pairs(child.embed_text)
                if indices:
                    named[BM25_NAME] = models.SparseVector(indices=indices, values=values)
                points.append(
                    models.PointStruct(
                        id=point_id_for(child.child_id),
                        vector=named,
                        payload=_payload(child, job_id),
                    )
                )
            for start in range(0, len(points), 64):
                self.client.upsert(collection_name=self.collection, points=points[start : start + 64])
        except Exception as exc:
            raise _qdrant_error(exc) from exc
        return len(children)

    def _search(
        self,
        query,
        using: str,
        limit: int,
        query_filter,
    ) -> list[ChildHit]:
        result = self.client.query_points(
            collection_name=self.collection,
            query=query,
            using=using,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        hits = []
        for point in result.points:
            payload = dict(point.payload or {})
            hit = _hit_from_payload(payload, float(point.score or 0.0))
            hit.bm25_hit = using == BM25_NAME
            if using == DENSE_NAME:
                hit.dense_score = float(point.score or 0.0)
            else:
                hit.dense_score = None
            hits.append(hit)
        return hits

    def query(
        self,
        vector: list[float],
        query_text: str,
        limit: int,
        prefetch: int,
        rrf_k: int,
        document_id: str | None = None,
    ) -> list[ChildHit]:
        models = self._models
        query_filter = None
        if document_id:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
            )
        try:
            dense_hits = self._search(vector, DENSE_NAME, prefetch, query_filter)
            indices, values = sparse_pairs(query_text)
            sparse_hits: list[ChildHit] = []
            if indices:
                sparse_hits = self._search(
                    models.SparseVector(indices=indices, values=values),
                    BM25_NAME,
                    prefetch,
                    query_filter,
                )
        except Exception as exc:
            raise _qdrant_error(exc) from exc
        if not sparse_hits:
            return dense_hits[:limit]
        return fuse_rrf(dense_hits, sparse_hits, rrf_k=rrf_k, limit=limit)


def get_chunk_store(settings: Settings) -> ChunkStore:
    url = (settings.qdrant_url or "").strip()
    if url.startswith("memory:"):
        return MemoryChunkStore.get(settings.qdrant_collection)
    return QdrantChunkStore(settings)
