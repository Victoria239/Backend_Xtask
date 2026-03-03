"""Projects service - Database repository."""

from typing import Any

from sqlalchemy import select, desc

from services.projects.models import Project
from shared.repository import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def get_all(self, filters: dict[str, Any] | None = None, **kwargs) -> list[Project]:
        """Override to support 'estado' and 'busqueda' filter aliases."""
        query = select(Project).order_by(desc(Project.created_at))
        if filters:
            if filters.get("estado"):
                query = query.where(Project.status == filters["estado"])
            if filters.get("busqueda"):
                query = query.where(Project.name.ilike(f"%{filters['busqueda']}%"))
            if filters.get("status"):
                query = query.where(Project.status == filters["status"])
        result = await self.db.execute(query)
        return list(result.scalars().all())
