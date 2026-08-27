from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rag_shared.core.errors import AppError
from rag_shared.models.entities import Department, User, UserDepartmentAssignment
from rag_shared.models.enums import UserRole, UserStatus
from rag_shared.schemas.api import UserResponse


def to_user_response(user: User) -> UserResponse:
    department_ids = [a.department_id for a in user.department_assignments]
    return UserResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        department_ids=department_ids,
        status=user.status,
        is_super_admin_seed=user.is_super_admin_seed,
    )


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.department_assignments))
        .where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_or_create_department(db: AsyncSession, name: str) -> Department:
    result = await db.execute(select(Department).where(Department.name == name))
    department = result.scalar_one_or_none()
    if department:
        return department
    department = Department(name=name.strip())
    db.add(department)
    await db.flush()
    return department


async def _get_user_department_ids(db: AsyncSession, user_id: str) -> set[str]:
    result = await db.execute(
        select(UserDepartmentAssignment.department_id).where(
            UserDepartmentAssignment.user_id == user_id
        )
    )
    return set(result.scalars().all())


async def assign_user_to_department(
    db: AsyncSession,
    *,
    user: User,
    department: Department,
    replace: bool = False,
) -> None:
    if replace:
        result = await db.execute(
            select(UserDepartmentAssignment).where(UserDepartmentAssignment.user_id == user.id)
        )
        for assignment in result.scalars().all():
            await db.delete(assignment)
        await db.flush()
        existing: set[str] = set()
    else:
        existing = await _get_user_department_ids(db, user.id)

    if department.id not in existing:
        db.add(UserDepartmentAssignment(user_id=user.id, department_id=department.id))
        await db.flush()


async def create_admin(
    db: AsyncSession,
    *,
    name: str,
    email: str,
    department_name: str,
) -> User:
    existing = await get_user_by_email(db, email)
    if existing and existing.role != UserRole.ADMIN:
        raise AppError("USER_ALREADY_EXISTS", "Email already registered with incompatible role.")

    department = await get_or_create_department(db, department_name)
    if existing:
        existing.name = name
        existing.status = UserStatus.ACTIVE
        await assign_user_to_department(db, user=existing, department=department)
        await db.refresh(existing, attribute_names=["department_assignments"])
        return existing

    user = User(
        email=email.lower(),
        name=name,
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    await assign_user_to_department(db, user=user, department=department)
    await db.refresh(user, attribute_names=["department_assignments"])
    return user


async def create_user_in_department(
    db: AsyncSession,
    *,
    name: str,
    email: str,
    department: Department,
) -> User:
    existing = await get_user_by_email(db, email)
    if existing and existing.role != UserRole.USER:
        raise AppError("USER_ALREADY_EXISTS", "Email already registered with incompatible role.")

    if existing:
        existing.name = name
        existing.status = UserStatus.ACTIVE
        await assign_user_to_department(db, user=existing, department=department)
        await db.refresh(existing, attribute_names=["department_assignments"])
        return existing

    user = User(
        email=email.lower(),
        name=name,
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()
    await assign_user_to_department(db, user=user, department=department)
    await db.refresh(user, attribute_names=["department_assignments"])
    return user


async def list_department_users(db: AsyncSession, department_id: str, role: UserRole | None = None) -> list[User]:
    stmt = (
        select(User)
        .join(UserDepartmentAssignment)
        .options(selectinload(User.department_assignments))
        .where(UserDepartmentAssignment.department_id == department_id)
    )
    if role:
        stmt = stmt.where(User.role == role)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def list_all_admins(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.department_assignments).selectinload(UserDepartmentAssignment.department)
        )
        .where(User.role == UserRole.ADMIN)
        .order_by(User.name)
    )
    return list(result.scalars().unique().all())


def to_admin_list_response(user: User) -> "AdminListResponse":
    from rag_shared.schemas.api import AdminListResponse

    department_names = [
        a.department.name for a in user.department_assignments if getattr(a, "department", None)
    ]
    return AdminListResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        department_ids=[a.department_id for a in user.department_assignments],
        department_names=department_names,
        status=user.status,
        is_super_admin_seed=user.is_super_admin_seed,
    )
