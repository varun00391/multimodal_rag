from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_super_admin
from app.core.errors import AppError
from app.db.session import get_db
from app.models.entities import Department
from app.schemas.api import DepartmentCreate, DepartmentResponse

router = APIRouter(prefix="/departments", tags=["departments"])


def _department_response(dept: Department) -> DepartmentResponse:
    return DepartmentResponse(department_id=dept.id, name=dept.name)


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_super_admin),
) -> list[DepartmentResponse]:
    result = await db.execute(select(Department).order_by(Department.name))
    return [_department_response(d) for d in result.scalars().all()]


@router.post("", response_model=DepartmentResponse, status_code=201)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_super_admin),
) -> DepartmentResponse:
    existing = await db.execute(select(Department).where(Department.name == payload.name.strip()))
    if existing.scalar_one_or_none():
        raise AppError("USER_ALREADY_EXISTS", "Department with this name already exists.", status_code=409)
    department = Department(name=payload.name.strip())
    db.add(department)
    await db.commit()
    await db.refresh(department)
    return _department_response(department)


@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> DepartmentResponse:
    if not current.is_super_admin and department_id not in current.department_ids:
        raise AppError("NOT_AUTHORIZED", "You cannot access this department.", status_code=403)

    result = await db.execute(select(Department).where(Department.id == department_id))
    department = result.scalar_one_or_none()
    if not department:
        raise AppError("DEPARTMENT_NOT_FOUND", "Department not found.", status_code=404)
    return _department_response(department)
