"""Projects service - Database repository."""

from typing import Any

from sqlalchemy import func, select

from services.projects.models import Project
from shared.repository import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    def _apply_filters(self, query, filters: dict[str, Any] | None = None):
        """Support 'estado' and 'busqueda' filter aliases."""
        if filters:
            if filters.get("estado"):
                query = query.where(Project.status == filters["estado"])
            if filters.get("busqueda"):
                query = query.where(Project.name.ilike(f"%{filters['busqueda']}%"))
            if filters.get("status"):
                query = query.where(Project.status == filters["status"])
        return query

    async def get_indicators(self) -> dict[str, int]:
        """Return project counts by status using SQL aggregation."""
        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Project.status == "active").label("active"),
                func.count().filter(Project.status == "completed").label("completed"),
            ).select_from(Project)
        )
        row = result.one()
        return {
            "total": row.total,
            "activos": row.active,
            "completados": row.completed,
            "enProgreso": row.total - row.active - row.completed,
        }
