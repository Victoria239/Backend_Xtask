"""Employees service - API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_user_id,
    get_optional_tenant_id,
    require_admin,
    require_manager,
)
from shared.schemas import PaginatedResponse
from services.employees.repository import EmployeeRepository
from services.employees.service import EmployeeService
from services.employees.schemas import (
    EmployeeCreate,
    EmployeeDocumentCreate,
    EmployeeDocumentOut,
    EmployeeUpdate,
    EmployeeOut,
    EmployeeProjectAssign,
    OrgNode,
)

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("employees"))) -> EmployeeService:
    return EmployeeService(EmployeeRepository(db))


@router.get("")
async def list_employees(
    department: str | None = Query(None),
    contract_status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
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
    return await service.list_employees_paginated(filters if filters else None, page, page_size)


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: int,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_employee(employee_id)


@router.post("", response_model=EmployeeOut, dependencies=[Depends(require_manager)])
async def create_employee(
    data: EmployeeCreate,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
    tenant_id: int | None = Depends(get_optional_tenant_id),
):
    return await service.create_employee(data, tenant_id=tenant_id)


@router.patch("/{employee_id}", response_model=EmployeeOut, dependencies=[Depends(require_manager)])
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_employee(employee_id, data)


@router.delete("/{employee_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_employee(
    employee_id: int,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_employee(employee_id)


@router.put("/{employee_id}/proyectos", dependencies=[Depends(require_manager)])
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


# ─── H-01: org chart ────────────────────────────────────────────
@router.get("/org-chart/tree", response_model=list[OrgNode])
async def org_chart(
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
    tenant_id: int | None = Depends(get_optional_tenant_id),
):
    return await service.get_org_chart(tenant_id=tenant_id)


# ─── H-01: employee documents ──────────────────────────────────
@router.post(
    "/{employee_id}/documents",
    response_model=EmployeeDocumentOut,
    dependencies=[Depends(require_manager)],
)
async def add_employee_document(
    employee_id: int,
    data: EmployeeDocumentCreate,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
    tenant_id: int | None = Depends(get_optional_tenant_id),
):
    return await service.add_document(employee_id, data, tenant_id=tenant_id)


@router.get("/{employee_id}/documents", response_model=list[EmployeeDocumentOut])
async def list_employee_documents(
    employee_id: int,
    service: EmployeeService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_documents(employee_id)
