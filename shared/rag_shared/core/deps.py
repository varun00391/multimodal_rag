from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rag_shared.core.errors import AppError
from rag_shared.db.session import get_db
from rag_shared.models.entities import User, UserDepartmentAssignment
from rag_shared.models.enums import UserRole, UserStatus
from rag_shared.schemas.enums import UserRole as UserRoleSchema


@dataclass
class CurrentUser:
    user: User
    department_ids: list[str]

    @property
    def user_id(self) -> str:
        return self.user.id

    @property
    def role(self) -> UserRole:
        return self.user.role

    @property
    def is_super_admin(self) -> bool:
        return self.user.role == UserRole.SUPER_ADMIN

    @property
    def is_admin(self) -> bool:
        return self.user.role == UserRole.ADMIN

    @property
    def is_user(self) -> bool:
        return self.user.role == UserRole.USER

    def can_upload(self) -> bool:
        return self.user.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}

    def can_manage_admins(self) -> bool:
        return self.user.role == UserRole.SUPER_ADMIN

    def can_manage_users_in_department(self, department_id: str) -> bool:
        if self.is_super_admin:
            return True
        return self.is_admin and department_id in self.department_ids

    def can_access_department(self, department_id: str) -> bool:
        if self.is_super_admin:
            return True
        return department_id in self.department_ids


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    user_id = request.headers.get("X-User-Id") or request.session.get("user_id")
    if not user_id:
        raise AppError("AUTH_REQUIRED", "Authentication is required.", status_code=401)

    result = await db.execute(
        select(User)
        .options(selectinload(User.department_assignments))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AppError("AUTH_INVALID", "Session is invalid.", status_code=401)
    if user.status != UserStatus.ACTIVE:
        raise AppError("NOT_AUTHORIZED", "User account is inactive.", status_code=403)

    department_ids = [a.department_id for a in user.department_assignments]
    return CurrentUser(user=user, department_ids=department_ids)


def require_roles(*roles: UserRoleSchema):
    async def _dependency(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.role.value not in {r.value for r in roles}:
            raise AppError("NOT_AUTHORIZED", "You are not authorized for this operation.", status_code=403)
        return current

    return _dependency


def require_upload_permission(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not current.can_upload():
        raise AppError(
            "NOT_AUTHORIZED",
            "Only Super Admin and Admin can upload or manage documents.",
            status_code=403,
        )
    return current


def require_super_admin(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not current.is_super_admin:
        raise AppError("NOT_AUTHORIZED", "Super Admin access required.", status_code=403)
    return current
