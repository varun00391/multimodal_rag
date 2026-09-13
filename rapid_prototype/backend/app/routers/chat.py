import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Conversation, Message, User
from app.schemas import ChatRequest, ChatResponse
from app.services.rag import AVAILABLE_MODELS, ask

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/models")
def models():
    return {"models": AVAILABLE_MODELS}


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = ask(db, user, body.message, body.conversation_id, body.model, body.source_filter)
    return result


@router.get("/conversations")
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in rows
    ]


@router.get("/conversations/{convo_id}")
def conversation_detail(
    convo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    convo = db.get(Conversation, convo_id)
    if not convo or convo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == convo.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return {
        "id": convo.id,
        "title": convo.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources_json or "[]"),
                "model": m.model,
                "latency_ms": m.latency_ms,
                "tokens_in": m.tokens_in,
                "tokens_out": m.tokens_out,
                "cost_usd": m.cost_usd,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.delete("/conversations/{convo_id}")
def delete_conversation(
    convo_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    convo = db.get(Conversation, convo_id)
    if not convo or convo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(convo)
    db.commit()
    return {"ok": True}
