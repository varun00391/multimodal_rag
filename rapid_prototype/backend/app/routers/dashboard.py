from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Conversation, Document, Message, UsageEvent, User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    events = db.query(UsageEvent).filter(UsageEvent.user_id == user.id).all()
    queries = [e for e in events if e.event_type == "query"]
    total_queries = len(queries)
    tokens_in = sum(e.tokens_in for e in queries)
    tokens_out = sum(e.tokens_out for e in queries)
    total_tokens = tokens_in + tokens_out
    total_cost = round(sum(e.cost_usd for e in queries), 6)
    avg_latency = round(sum(e.latency_ms for e in queries) / total_queries, 1) if queries else 0

    model_map: dict[str, dict] = {}
    for e in queries:
        bucket = model_map.setdefault(
            e.model or "unknown",
            {"model": e.model or "unknown", "queries": 0, "tokens": 0, "cost_usd": 0.0},
        )
        bucket["queries"] += 1
        bucket["tokens"] += e.tokens_in + e.tokens_out
        bucket["cost_usd"] = round(bucket["cost_usd"] + e.cost_usd, 6)
    model_distribution = sorted(model_map.values(), key=lambda x: x["queries"], reverse=True)

    day_map: dict[str, dict] = {}
    for e in queries:
        key = (e.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
        bucket = day_map.setdefault(key, {"date": key, "queries": 0, "tokens": 0, "cost_usd": 0.0, "latency_sum": 0})
        bucket["queries"] += 1
        bucket["tokens"] += e.tokens_in + e.tokens_out
        bucket["cost_usd"] = round(bucket["cost_usd"] + e.cost_usd, 6)
        bucket["latency_sum"] += e.latency_ms
    series = []
    start = datetime.utcnow().date() - timedelta(days=27)
    for i in range(28):
        day = (start + timedelta(days=i)).isoformat()
        row = day_map.get(day, {"date": day, "queries": 0, "tokens": 0, "cost_usd": 0.0, "latency_sum": 0})
        latency = round(row["latency_sum"] / row["queries"], 1) if row["queries"] else 0
        series.append(
            {
                "date": day,
                "queries": row["queries"],
                "tokens": row["tokens"],
                "cost_usd": row["cost_usd"],
                "avg_latency_ms": latency,
            }
        )

    recent = (
        db.query(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user.id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(12)
        .all()
    )
    questions = [
        {
            "id": msg.id,
            "question": msg.content,
            "conversation_id": convo.id,
            "title": convo.title,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        for msg, convo in recent
    ]

    doc_count = db.query(func.count(Document.id)).filter(Document.user_id == user.id).scalar() or 0
    convo_count = db.query(func.count(Conversation.id)).filter(Conversation.user_id == user.id).scalar() or 0
    modality_rows = (
        db.query(Document.modality, func.count(Document.id))
        .filter(Document.user_id == user.id)
        .group_by(Document.modality)
        .all()
    )

    return {
        "kpis": {
            "questions": total_queries,
            "tokens": total_tokens,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "avg_latency_ms": avg_latency,
            "total_cost_usd": total_cost,
            "documents": doc_count,
            "conversations": convo_count,
        },
        "model_distribution": model_distribution,
        "usage_series": series,
        "recent_questions": questions,
        "modality_breakdown": [{"modality": m, "count": c} for m, c in modality_rows],
    }
