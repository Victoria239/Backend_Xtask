"""Projects service - Database repository."""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.projects.models import Project


class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, filters: dict | None = None) -> list[Project]:
        query = select(Project).order_by(desc(Project.created_at))
        if filters:
            if filters.get("estado"):
                query = query.where(Project.status == filters["estado"])
            if filters.get("busqueda"):
                query = query.where(Project.name.ilike(f"%{filters['busqueda']}%"))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, project_id: int) -> Project | None:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Project:
        project = Project(**data)
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def update(self, project_id: int, data: dict) -> Project | None:
        project = await self.get_by_id(project_id)
        if not project:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(project, key, value)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def delete(self, project_id: int) -> bool:
        project = await self.get_by_id(project_id)
        if not project:
            return False
        await self.db.delete(project)
        await self.db.flush()
        return True
