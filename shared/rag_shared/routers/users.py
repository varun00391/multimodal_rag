from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rag_shared.core.deps import CurrentUser, get_current_user, require_super_admin
from rag_shared.core.errors import AppError
from rag_shared.db.session import get_db
from rag_shared.models.entities import Department, User, UserDepartmentAssignment
from rag_shared.models.enums import UserRole, UserStatus
from rag_shared.schemas.api import UserCreate, UserDepartmentUpdate, UserResponse, UserStatusUpdate
from rag_shared.services.audit import write_audit_log
from rag_shared.services.users import (
    assign_user_to_department,
    create_user_in_department,
    list_department_users,
    to_user_response,
)

router = APIRouter(tags=["users"])


async def _get_department(db: AsyncSession, department_id: str) -> Department:
    result = await db.execute(select(Department).where(Department.id == department_id))
    department = result.scalar_one_or_none()
    if not department:
        raise AppError("DEPARTMENT_NOT_FOUND", "Department not found.", status_code=404)
    return department


@router.get("/departments/{department_id}/users", response_model=list[UserResponse])
async def list_users_in_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[UserResponse]:
    if not current.can_manage_users_in_department(department_id):
        raise AppError("NOT_AUTHORIZED", "You cannot view users in this department.", status_code=403)
    users = await list_department_users(db, department_id, role=UserRole.USER)
    return [to_user_response(u) for u in users]


@router.post("/departments/{department_id}/users", response_model=UserResponse, status_code=201)
async def create_user(
    department_id: str,
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    if not current.can_manage_users_in_department(department_id):
        raise AppError("NOT_AUTHORIZED", "You cannot add users to this department.", status_code=403)

    department = await _get_department(db, department_id)
    user = await create_user_in_department(
        db,
        name=payload.name,
        email=str(payload.email),
        department=department,
    )
    await write_audit_log(
        db,
        event_type="USER_CREATED",
        actor_user_id=current.user_id,
        resource_type="user",
        resource_id=user.id,
        details={"department_id": department_id, "email": user.email},
    )
    await db.commit()
    return to_user_response(user)


@router.delete("/departments/{department_id}/users/{user_id}", status_code=204)
async def remove_user_from_department(
    department_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> None:
    if not current.can_manage_users_in_department(department_id):
        raise AppError("NOT_AUTHORIZED", "You cannot remove users from this department.", status_code=403)

    result = await db.execute(
        select(User)
        .options(selectinload(User.department_assignments))
        .where(User.id == user_id, User.role == UserRole.USER)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AppError("DOCUMENT_NOT_FOUND", "User not found.", status_code=404)

    assignment = next((a for a in user.department_assignments if a.department_id == department_id), None)
    if assignment:
        await db.delete(assignment)
    if not user.department_assignments:
        user.status = UserStatus.INACTIVE
    await write_audit_log(
        db,
        event_type="USER_REMOVED",
        actor_user_id=current.user_id,
        resource_type="user",
        resource_id=user.id,
        details={"department_id": department_id},
    )
    await db.commit()


@router.patch("/users/{user_id}/department", response_model=UserResponse)
async def change_user_department(
    user_id: str,
    payload: UserDepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_super_admin),
) -> UserResponse:
    result = await db.execute(
        select(User)
        .options(selectinload(User.department_assignments))
        .where(User.id == user_id, User.role == UserRole.USER)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AppError("DOCUMENT_NOT_FOUND", "User not found.", status_code=404)

    department = await _get_department(db, payload.department_id)
    await assign_user_to_department(db, user=user, department=department, replace=True)
    await write_audit_log(
        db,
        event_type="USER_DEPARTMENT_CHANGED",
        actor_user_id=current.user_id,
        resource_type="user",
        resource_id=user.id,
        details={"department_id": payload.department_id},
    )
    await db.commit()
    await db.refresh(user, attribute_names=["department_assignments"])
    return to_user_response(user)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    result = await db.execute(
        select(User)
        .options(selectinload(User.department_assignments))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AppError("DOCUMENT_NOT_FOUND", "User not found.", status_code=404)
    if user.is_super_admin_seed:
        raise AppError("NOT_AUTHORIZED", "Seed Super Admin status cannot be changed.", status_code=403)

    if current.is_super_admin:
        pass
    elif current.is_admin:
        if user.role != UserRole.USER:
            raise AppError("NOT_AUTHORIZED", "Admin can only manage Users.", status_code=403)
        if not any(d in current.department_ids for d in [a.department_id for a in user.department_assignments]):
            raise AppError("NOT_AUTHORIZED", "User is outside your department scope.", status_code=403)
    else:
        raise AppError("NOT_AUTHORIZED", "You cannot change user status.", status_code=403)

    user.status = payload.status
    await db.commit()
    await db.refresh(user, attribute_names=["department_assignments"])
    return to_user_response(user)
