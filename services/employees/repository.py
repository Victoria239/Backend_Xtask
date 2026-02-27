"""Employees service - Database repository."""

from sqlalchemy import select, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession

from services.employees.models import Employee, EmployeeProject


class EmployeeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, filters: dict | None = None) -> list[Employee]:
        query = select(Employee).order_by(desc(Employee.created_at))
        if filters:
            if filters.get("department"):
                query = query.where(Employee.department == filters["department"])
            if filters.get("contract_status"):
                query = query.where(Employee.contract_status == filters["contract_status"])
            if filters.get("search"):
                search = f"%{filters['search']}%"
                query = query.where(
                    (Employee.first_name.ilike(search)) | (Employee.last_name.ilike(search))
                )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, employee_id: int) -> Employee | None:
        result = await self.db.execute(select(Employee).where(Employee.id == employee_id))
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> Employee | None:
        result = await self.db.execute(select(Employee).where(Employee.user_id == user_id))
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Employee:
        employee = Employee(**data)
        self.db.add(employee)
        await self.db.flush()
        await self.db.refresh(employee)
        return employee

    async def update(self, employee_id: int, data: dict) -> Employee | None:
        employee = await self.get_by_id(employee_id)
        if not employee:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(employee, key, value)
        await self.db.flush()
        await self.db.refresh(employee)
        return employee

    async def delete(self, employee_id: int) -> bool:
        employee = await self.get_by_id(employee_id)
        if not employee:
            return False
        # Delete project assignments first
        await self.db.execute(
            delete(EmployeeProject).where(EmployeeProject.employee_id == employee_id)
        )
        await self.db.delete(employee)
        await self.db.flush()
        return True

    async def assign_projects(self, employee_id: int, project_ids: list[int]) -> None:
        # Remove existing assignments
        await self.db.execute(
            delete(EmployeeProject).where(EmployeeProject.employee_id == employee_id)
        )
        # Add new assignments
        for project_id in project_ids:
            assignment = EmployeeProject(employee_id=employee_id, project_id=project_id)
            self.db.add(assignment)
        await self.db.flush()

    async def get_project_ids(self, employee_id: int) -> list[int]:
        result = await self.db.execute(
            select(EmployeeProject.project_id).where(EmployeeProject.employee_id == employee_id)
        )
        return list(result.scalars().all())
