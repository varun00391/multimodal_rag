from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import ConnectorConnectRequest
from app.services.connectors import connect_provider, disconnect_provider, list_connectors, sync_provider

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


@router.get("")
def list_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_connectors(db, user)


@router.post("/{provider}/connect")
def connect(
    provider: str,
    body: ConnectorConnectRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = connect_provider(db, user, provider, body.account_email if body else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "provider": row.provider,
        "status": row.status,
        "account_email": row.account_email,
        "items_synced": row.items_synced,
    }


@router.post("/{provider}/disconnect")
def disconnect(provider: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    disconnect_provider(db, user, provider)
    return {"ok": True, "provider": provider, "status": "disconnected"}


@router.post("/{provider}/sync")
def sync(provider: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return sync_provider(db, user, provider)
