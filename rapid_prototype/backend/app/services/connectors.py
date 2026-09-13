from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Chunk, Connector, Document, User

CATALOG = [
    {
        "provider": "gdrive",
        "name": "Google Drive",
        "description": "Pull docs, slides, sheets, and PDFs from Drive folders.",
        "category": "files",
    },
    {
        "provider": "gmail",
        "name": "Gmail",
        "description": "Index threads so you can ask about invoices, briefs, and follow-ups.",
        "category": "mail",
    },
    {
        "provider": "outlook",
        "name": "Outlook",
        "description": "Sync mail and calendar notes from Microsoft 365.",
        "category": "mail",
    },
    {
        "provider": "onedrive",
        "name": "OneDrive",
        "description": "Ingest shared work files from OneDrive for Business.",
        "category": "files",
    },
    {
        "provider": "dropbox",
        "name": "Dropbox",
        "description": "Bring in shared folders, design exports, and archives.",
        "category": "files",
    },
    {
        "provider": "slack",
        "name": "Slack",
        "description": "Search decisions and incident threads across channels.",
        "category": "chat",
    },
    {
        "provider": "notion",
        "name": "Notion",
        "description": "Retrieve wiki pages, specs, and meeting notes.",
        "category": "wiki",
    },
    {
        "provider": "sharepoint",
        "name": "SharePoint",
        "description": "Enterprise libraries and policy document sets.",
        "category": "files",
    },
]


SAMPLE_ITEMS = {
    "gdrive": [
        (
            "Northstar_PRD.docx",
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Product requirements: Nexus must ingest PDFs, images, and video, then answer with citations. "
            "Launch gate is connector coverage for Drive, Gmail, and Outlook.",
        ),
        (
            "Architecture_Diagram.png",
            "image",
            "image/png",
            "Image of the Nexus architecture: ingest workers write chunks to the knowledge store; "
            "the query plane retrieves, reranks, and calls the LLM gateway.",
        ),
        (
            "Security_Whitepaper.pdf",
            "pdf",
            "application/pdf",
            "Nexus isolates tenants, encrypts files at rest, and supports SAML SSO. "
            "Data residency can be pinned to US or EU regions.",
        ),
    ],
    "gmail": [
        (
            "Invoice from Helios Labs.eml",
            "text",
            "message/rfc822",
            "From billing@helios.example: Invoice #HL-2044 for $12,400 due 30 Sep. "
            "PO-881 referenced. Contact ap@acme.com for disputes.",
        ),
        (
            "Re: Q3 board pack.eml",
            "text",
            "message/rfc822",
            "Board pack attached. Highlight multimodal RAG prototype, 2.1s average latency, "
            "and 18 connected Drive folders. Ask Ada for the dashboard screenshots.",
        ),
        (
            "Customer SSO follow-up.eml",
            "text",
            "message/rfc822",
            "Following the call recording, send the security whitepaper and confirm SAML metadata exchange by Friday.",
        ),
    ],
    "outlook": [
        (
            "Weekly ops review.msg",
            "text",
            "application/vnd.ms-outlook",
            "Outlook calendar notes: warehouse SKU-4410 is below safety stock. Night shift photo is in the library. "
            "Action: restock aisle B12.",
        ),
        (
            "Refund policy clarification.msg",
            "text",
            "application/vnd.ms-outlook",
            "Refunds are issued within 14 days for unused seats. Enterprise contracts use a 30-day clause. "
            "Escalate exceptions to finance@acme.com.",
        ),
    ],
    "onedrive": [
        (
            "Employee_Handbook.pdf",
            "pdf",
            "application/pdf",
            "Remote work stipend is $150/month. VPN is required off-network. "
            "Ask Nexus about PPE rules before visiting the warehouse.",
        )
    ],
    "dropbox": [
        (
            "Brand_Guidelines.pdf",
            "pdf",
            "application/pdf",
            "Primary type is Plus Jakarta Sans. Accent color is chartreuse on ink. "
            "Do not use generic purple gradients on marketing slides.",
        )
    ],
    "slack": [
        (
            "incidents-ask-nexus.txt",
            "text",
            "text/plain",
            "Slack #incidents: p95 latency spiked to 3.8s after a large Drive sync. "
            "Mitigation: batch embeddings and cache TF-IDF rebuilds per user.",
        )
    ],
    "notion": [
        (
            "Refund Policy.md",
            "text",
            "text/markdown",
            "Notion wiki: Standard refund window is 14 days. Enterprise is 30 days. "
            "Unused seats only. File requests through finance@acme.com.",
        )
    ],
    "sharepoint": [
        (
            "ISO27001_Controls.xlsx",
            "spreadsheet",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Control A.8.2 requires access reviews quarterly. Evidence lives in the security whitepaper "
            "and SAML configuration runbook.",
        )
    ],
}


def list_connectors(db: Session, user: User) -> list[dict]:
    existing = {c.provider: c for c in db.query(Connector).filter(Connector.user_id == user.id).all()}
    out = []
    for item in CATALOG:
        row = existing.get(item["provider"])
        out.append(
            {
                **item,
                "status": row.status if row else "disconnected",
                "account_email": row.account_email if row else "",
                "items_synced": row.items_synced if row else 0,
                "last_synced_at": row.last_synced_at.isoformat() if row and row.last_synced_at else None,
                "id": row.id if row else None,
            }
        )
    return out


def _get_or_create(db: Session, user_id: int, provider: str) -> Connector:
    row = (
        db.query(Connector)
        .filter(Connector.user_id == user_id, Connector.provider == provider)
        .first()
    )
    if not row:
        row = Connector(user_id=user_id, provider=provider, status="disconnected")
        db.add(row)
        db.flush()
    return row


def connect_provider(db: Session, user: User, provider: str, account_email: str | None) -> Connector:
    if provider not in {c["provider"] for c in CATALOG}:
        raise ValueError("Unknown connector")
    row = _get_or_create(db, user.id, provider)
    row.status = "connected"
    row.account_email = account_email or user.email
    db.commit()
    db.refresh(row)
    return row


def disconnect_provider(db: Session, user: User, provider: str) -> None:
    row = (
        db.query(Connector)
        .filter(Connector.user_id == user.id, Connector.provider == provider)
        .first()
    )
    if not row:
        return
    docs = (
        db.query(Document)
        .filter(Document.user_id == user.id, Document.source == provider)
        .all()
    )
    for doc in docs:
        db.delete(doc)
    row.status = "disconnected"
    row.items_synced = 0
    row.last_synced_at = None
    db.commit()


def sync_provider(db: Session, user: User, provider: str) -> dict:
    row = _get_or_create(db, user.id, provider)
    if row.status != "connected":
        row.status = "connected"
        row.account_email = row.account_email or user.email
    items = SAMPLE_ITEMS.get(provider, [])
    created = 0
    for name, modality, mime, text in items:
        exists = (
            db.query(Document)
            .filter(
                Document.user_id == user.id,
                Document.source == provider,
                Document.original_name == name,
            )
            .first()
        )
        if exists:
            continue
        doc = Document(
            user_id=user.id,
            filename=name,
            original_name=name,
            mime_type=mime,
            size_bytes=len(text.encode()),
            modality=modality,
            source=provider,
            status="ready",
            extra_json=json.dumps({"connector": provider, "simulated": True}),
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
        created += 1
    row.items_synced = (
        db.query(Document)
        .filter(Document.user_id == user.id, Document.source == provider)
        .count()
    )
    row.last_synced_at = datetime.utcnow()
    db.commit()
    return {"provider": provider, "created": created, "items_synced": row.items_synced}
