from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rag_shared.core.deps import CurrentUser, require_super_admin
from rag_shared.core.errors import AppError
from rag_shared.db.session import get_db
from rag_shared.models.entities import Department, User, UserDepartmentAssignment
from rag_shared.models.enums import UserRole
from rag_shared.schemas.api import AdminCreate, AdminListResponse, UserResponse
from rag_shared.services.audit import write_audit_log
from rag_shared.services.users import create_admin, list_all_admins, list_department_users, to_admin_list_response, to_user_response

router = APIRouter(tags=["admins"])


@router.get("/admins", response_model=list[AdminListResponse])
async def list_admins(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_super_admin),
) -> list[AdminListResponse]:
    users = await list_all_admins(db)
    return [to_admin_list_response(u) for u in users]


@router.post("/admins", response_model=UserResponse, status_code=201)
async def create_admin_user(
    payload: AdminCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
) -> UserResponse:
    user = await create_admin(
        db,
        name=payload.name,
        email=str(payload.email),
        department_name=payload.department_name,
    )
    await write_audit_log(
        db,
        event_type="ADMIN_CREATED",
        actor_user_id=current.user_id,
        resource_type="user",
        resource_id=user.id,
        details={"email": user.email, "department_name": payload.department_name},
    )
    await db.commit()
    return to_user_response(user)


@router.get("/departments/{department_id}/admins", response_model=list[UserResponse])
async def list_department_admins(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_super_admin),
) -> list[UserResponse]:
    users = await list_department_users(db, department_id, role=UserRole.ADMIN)
    return [to_user_response(u) for u in users]


@router.delete("/departments/{department_id}/admins/{user_id}", status_code=204)
async def remove_department_admin(
    department_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
) -> None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.department_assignments))
        .where(User.id == user_id, User.role == UserRole.ADMIN)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AppError("DOCUMENT_NOT_FOUND", "Admin not found.", status_code=404)
    if user.is_super_admin_seed:
        raise AppError("NOT_AUTHORIZED", "Seed Super Admin cannot be removed.", status_code=403)

    assignment = next((a for a in user.department_assignments if a.department_id == department_id), None)
    if assignment:
        await db.delete(assignment)
    from rag_shared.models.enums import UserStatus

    user.status = UserStatus.INACTIVE
    await write_audit_log(
        db,
        event_type="ADMIN_REMOVED",
        actor_user_id=current.user_id,
        resource_type="user",
        resource_id=user.id,
        details={"department_id": department_id},
    )
    await db.commit()
