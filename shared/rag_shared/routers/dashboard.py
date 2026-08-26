from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_shared.core.deps import CurrentUser, get_current_user, require_super_admin
from rag_shared.core.errors import AppError
from rag_shared.db.session import get_db
from rag_shared.models.entities import Document, QueryRecord, User, UserDepartmentAssignment
from rag_shared.models.enums import UserRole

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/me")
async def user_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> dict:
    query_count = await db.scalar(
        select(func.count()).select_from(QueryRecord).where(QueryRecord.user_id == current.user_id)
    )
    return {
        "role": current.role.value,
        "query_count": query_count or 0,
        "department_ids": current.department_ids,
    }


@router.get("/departments/{department_id}")
async def department_dashboard(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> dict:
    if not current.is_super_admin and department_id not in current.department_ids:
        raise AppError("NOT_AUTHORIZED", "You cannot view this department dashboard.", status_code=403)

    user_count = await db.scalar(
        select(func.count())
        .select_from(UserDepartmentAssignment)
        .join(User)
        .where(
            UserDepartmentAssignment.department_id == department_id,
            User.role == UserRole.USER,
        )
    )
    document_count = await db.scalar(
        select(func.count()).select_from(Document).where(Document.department_id == department_id)
    )
    query_count = await db.scalar(
        select(func.count())
        .select_from(QueryRecord)
        .join(User, QueryRecord.user_id == User.id)
        .join(UserDepartmentAssignment, UserDepartmentAssignment.user_id == User.id)
        .where(UserDepartmentAssignment.department_id == department_id)
    )
    return {
        "department_id": department_id,
        "users": user_count or 0,
        "documents": document_count or 0,
        "queries": query_count or 0,
    }


@router.get("/super-admin")
async def super_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_super_admin),
) -> dict:
    users_by_role = {}
    for role in UserRole:
        count = await db.scalar(select(func.count()).select_from(User).where(User.role == role))
        users_by_role[role.value] = count or 0

    document_count = await db.scalar(select(func.count()).select_from(Document))
    query_count = await db.scalar(select(func.count()).select_from(QueryRecord))
    return {
        "users_by_role": users_by_role,
        "documents": document_count or 0,
        "queries": query_count or 0,
    }
