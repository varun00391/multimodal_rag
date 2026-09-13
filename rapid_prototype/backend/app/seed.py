from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Chunk, Connector, Conversation, Document, Message, UsageEvent, User
from app.services.connectors import SAMPLE_ITEMS

DEMO_DOCS = [
    {
        "original_name": "Q3_Product_Strategy.pdf",
        "modality": "pdf",
        "source": "upload",
        "mime_type": "application/pdf",
        "text": (
            "Nexus Q3 Product Strategy. Goal: ship multimodal retrieval for PDFs, images, and video. "
            "Priority features: connector sync for Google Drive and Gmail, usage dashboard with token "
            "and cost tracking, and cited answers. Success metric: p95 latency under 2.5 seconds. "
            "Budget owner: finance@acme.com. The knowledge OS should treat every file type as a first-class source."
        ),
    },
    {
        "original_name": "onboarding_runbook.md",
        "modality": "text",
        "source": "upload",
        "mime_type": "text/markdown",
        "text": (
            "New teammate onboarding: 1) Create a Nexus account. 2) Upload policy PDFs and screenshots. "
            "3) Connect Google Drive and Outlook. 4) Ask 'What is our refund policy?' to verify retrieval. "
            "Support hours are 9am-6pm IST. Incident channel is #ask-nexus."
        ),
    },
    {
        "original_name": "warehouse_floor.jpg",
        "modality": "image",
        "source": "upload",
        "mime_type": "image/jpeg",
        "text": (
            "Image description: warehouse aisle B12 with palletized SKU-4410 boxes. Safety sign reads "
            "'PPE required beyond this point'. Last inventory count: 1,240 units. Photographed during night shift."
        ),
    },
    {
        "original_name": "customer_call_clip.mp4",
        "modality": "video",
        "source": "upload",
        "mime_type": "video/mp4",
        "text": (
            "Video transcript excerpt: Customer asked about enterprise SSO and data residency. "
            "Account executive said Nexus supports SAML and keeps tenant data isolated. "
            "Follow-up: send security whitepaper by Friday."
        ),
    },
]


def seed_demo_user(db: Session, user: User) -> None:
    for i, spec in enumerate(DEMO_DOCS):
        doc = Document(
            user_id=user.id,
            filename=spec["original_name"],
            original_name=spec["original_name"],
            mime_type=spec["mime_type"],
            size_bytes=4200 + i * 800,
            modality=spec["modality"],
            source=spec["source"],
            status="ready",
            extra_json=json.dumps({"seeded": True}),
        )
        db.add(doc)
        db.flush()
        db.add(
            Chunk(
                document_id=doc.id,
                user_id=user.id,
                content=spec["text"],
                chunk_index=0,
                modality=spec["modality"],
            )
        )

    for provider, email in [("gdrive", "ada@acme.com"), ("gmail", "ada@acme.com"), ("outlook", "ada@acme.com")]:
        count = 0
        for name, modality, mime, text in SAMPLE_ITEMS.get(provider, []):
            doc = Document(
                user_id=user.id,
                filename=name,
                original_name=name,
                mime_type=mime,
                size_bytes=len(text.encode()),
                modality=modality,
                source=provider,
                status="ready",
                extra_json=json.dumps({"connector": provider, "seeded": True}),
            )
            db.add(doc)
            db.flush()
            db.add(
                Chunk(
                    document_id=doc.id,
                    user_id=user.id,
                    content=text,
                    chunk_index=0,
                    modality=modality,
                )
            )
            count += 1
        db.add(
            Connector(
                user_id=user.id,
                provider=provider,
                status="connected",
                account_email=email,
                items_synced=count,
                last_synced_at=datetime.utcnow() - timedelta(hours=6),
            )
        )

    convo = Conversation(user_id=user.id, title="Refund policy and SSO")
    db.add(convo)
    db.flush()
    db.add(
        Message(
            conversation_id=convo.id,
            role="user",
            content="What did the customer ask about in the call recording?",
        )
    )
    db.add(
        Message(
            conversation_id=convo.id,
            role="assistant",
            content="They asked about enterprise SSO and data residency. The AE confirmed SAML support and tenant isolation, and promised the security whitepaper by Friday.",
            sources_json=json.dumps(
                [{"filename": "customer_call_clip.mp4", "modality": "video", "source": "upload"}]
            ),
            model="gpt-4o-mini",
            latency_ms=1180,
            tokens_in=640,
            tokens_out=92,
            cost_usd=0.00021,
        )
    )

    models = [
        ("gpt-4o-mini", 0.55, 0.00018),
        ("gpt-4o", 0.22, 0.0042),
        ("claude-3.5-sonnet", 0.15, 0.0031),
        ("gemini-2.0-flash", 0.08, 0.00009),
    ]
    now = datetime.utcnow()
    for day in range(28):
        for model, share, unit_cost in models:
            queries = max(1, int(4 * share) + (day % 3))
            for q in range(queries):
                tokens_in = 380 + (day * 11 + q * 17) % 900
                tokens_out = 90 + (day * 7 + q * 13) % 220
                db.add(
                    UsageEvent(
                        user_id=user.id,
                        event_type="query",
                        model=model,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        latency_ms=700 + (day * 37 + q * 41) % 1600,
                        cost_usd=round((tokens_in + tokens_out) / 1000 * unit_cost, 6),
                        created_at=now - timedelta(days=27 - day, hours=q * 2),
                    )
                )
    db.commit()
