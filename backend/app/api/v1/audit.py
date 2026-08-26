from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_super_admin
from app.db.session import get_db
from app.schemas.api import AuditLogResponse
from app.services.audit import list_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[AuditLogResponse]:
    if not (current.is_super_admin or current.is_admin):
        from app.core.errors import AppError

        raise AppError("NOT_AUTHORIZED", "Audit logs require admin access.", status_code=403)

    logs = await list_audit_logs(db)
    return [
        AuditLogResponse(
            id=log.id,
            event_type=log.event_type,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
