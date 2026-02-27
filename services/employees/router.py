"""Employees service - API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id
from services.employees.repository import EmployeeRepository
from services.employees.service import EmployeeService
from services.employees.schemas import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeOut,
    EmployeeProjectAssign,
)

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> EmployeeService:
    return EmployeeService(EmployeeRepository(db))


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    department: str | None = Query(None),
    contract_status: str | None = Query(None),
    search: str | None = Query(None),
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    filters = {}
    if department:
        filters["department"] = department
    if contract_status:
        filters["contract_status"] = contract_status
    if search:
        filters["search"] = search
    return await service.list_employees(filters if filters else None)


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: int,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_employee(employee_id)


@router.post("", response_model=EmployeeOut)
async def create_employee(
    data: EmployeeCreate,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_employee(data)


@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_employee(employee_id, data)


@router.delete("/{employee_id}", status_code=204)
async def delete_employee(
    employee_id: int,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_employee(employee_id)


@router.put("/{employee_id}/proyectos")
async def assign_projects(
    employee_id: int,
    data: EmployeeProjectAssign,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.assign_projects(employee_id, data.project_ids)


@router.get("/{employee_id}/proyectos")
async def get_employee_projects(
    employee_id: int,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    project_ids = await service.get_project_ids(employee_id)
    return {"employee_id": employee_id, "project_ids": project_ids}
