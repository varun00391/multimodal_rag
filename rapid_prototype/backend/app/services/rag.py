from __future__ import annotations

import json
import time
from datetime import datetime

import httpx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Conversation, Document, Message, UsageEvent, User
from app.services.usage import estimate_cost, estimate_tokens

AVAILABLE_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "claude-3.5-sonnet",
    "gemini-2.0-flash",
    "nexus-extractive",
]


def retrieve(
    db: Session,
    user_id: int,
    query: str,
    source_filter: str | None = None,
    k: int = 6,
) -> list[tuple[Chunk, Document, float]]:
    q = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.user_id == user_id)
    )
    if source_filter and source_filter != "all":
        q = q.filter(Document.source == source_filter)
    rows = q.all()
    if not rows:
        return []
    corpus = [c.content for c, _ in rows]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=8000)
    try:
        matrix = vectorizer.fit_transform(corpus + [query])
    except ValueError:
        return [(c, d, 0.0) for c, d in rows[:k]]
    scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    ranked = sorted(zip(rows, scores, strict=True), key=lambda x: x[1], reverse=True)
    out = []
    for (chunk, doc), score in ranked[:k]:
        if score <= 0 and len(out) >= 2:
            continue
        out.append((chunk, doc, float(score)))
    return out


def _extractive_answer(query: str, hits: list[tuple[Chunk, Document, float]]) -> str:
    if not hits:
        return (
            "I could not find matching material in your library yet. "
            "Upload files or sync a connector, then ask again."
        )
    parts = [f"Based on your sources for “{query}”:"]
    for i, (chunk, doc, score) in enumerate(hits[:4], start=1):
        excerpt = chunk.content[:420].strip()
        parts.append(f"{i}. {doc.original_name} ({doc.modality}, {doc.source}) — {excerpt}")
    parts.append("Citations are attached so you can open the original files.")
    return "\n\n".join(parts)


def _llm_answer(query: str, hits: list[tuple[Chunk, Document, float]], model: str, api_key: str) -> str:
    context = "\n\n".join(
        f"[Source {i}] file={doc.original_name} type={doc.modality} origin={doc.source}\n{chunk.content[:1400]}"
        for i, (chunk, doc, _) in enumerate(hits, start=1)
    )
    prompt = (
        "You are Nexus, a multimodal RAG assistant. Answer only from the provided sources. "
        "If the sources do not contain the answer, say so. Cite filenames inline.\n\n"
        f"SOURCES:\n{context or '(none)'}\n\nQUESTION:\n{query}"
    )
    mapped = {
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4o": "gpt-4o",
        "claude-3.5-sonnet": "gpt-4o-mini",
        "gemini-2.0-flash": "gpt-4o-mini",
        "nexus-extractive": "extractive",
    }.get(model, "gpt-4o-mini")
    if mapped == "extractive" or not api_key:
        return _extractive_answer(query, hits)
    payload = {
        "model": mapped,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "Answer with grounded citations from the user's corpus."},
            {"role": "user", "content": prompt},
        ],
    }
    with httpx.Client(timeout=45.0) as client:
        resp = client.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def ask(
    db: Session,
    user: User,
    message: str,
    conversation_id: int | None,
    model: str | None,
    source_filter: str | None,
) -> dict:
    started = time.perf_counter()
    chosen = model or settings.default_model
    if chosen not in AVAILABLE_MODELS:
        chosen = settings.default_model

    if conversation_id:
        convo = db.get(Conversation, conversation_id)
        if not convo or convo.user_id != user.id:
            convo = Conversation(user_id=user.id, title=message[:72])
            db.add(convo)
            db.flush()
    else:
        convo = Conversation(user_id=user.id, title=message[:72])
        db.add(convo)
        db.flush()

    db.add(Message(conversation_id=convo.id, role="user", content=message))

    hits = retrieve(db, user.id, message, source_filter=source_filter)
    user_settings = json.loads(user.settings_json or "{}")
    api_key = user_settings.get("openai_api_key") or settings.openai_api_key
    used_model = chosen if api_key and chosen != "nexus-extractive" else "nexus-extractive"
    try:
        answer = _llm_answer(message, hits, chosen, api_key)
        if api_key and chosen != "nexus-extractive":
            used_model = chosen
    except Exception:
        answer = _extractive_answer(message, hits)
        used_model = "nexus-extractive"

    sources = [
        {
            "document_id": doc.id,
            "filename": doc.original_name,
            "modality": doc.modality,
            "source": doc.source,
            "excerpt": chunk.content[:280],
            "score": round(score, 4),
        }
        for chunk, doc, score in hits
    ]
    latency_ms = int((time.perf_counter() - started) * 1000)
    tokens_in = estimate_tokens(message + "".join(s["excerpt"] for s in sources))
    tokens_out = estimate_tokens(answer)
    cost = estimate_cost(used_model, tokens_in, tokens_out)

    db.add(
        Message(
            conversation_id=convo.id,
            role="assistant",
            content=answer,
            sources_json=json.dumps(sources),
            model=used_model,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
        )
    )
    db.add(
        UsageEvent(
            user_id=user.id,
            event_type="query",
            model=used_model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
        )
    )
    convo.title = convo.title or message[:72]
    convo.updated_at = datetime.utcnow()
    db.commit()
    return {
        "conversation_id": convo.id,
        "answer": answer,
        "sources": sources,
        "model": used_model,
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost,
    }
