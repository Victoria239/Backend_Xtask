"""Projects service - Business logic."""

from shared.exceptions import NotFoundException
from services.projects.models import Project
from services.projects.repository import ProjectRepository
from services.projects.schemas import ProjectCreate, ProjectUpdate, ProjectOut


class ProjectService:
    def __init__(self, repo: ProjectRepository):
        self.repo = repo

    async def list_projects(self, filters: dict | None = None) -> list[ProjectOut]:
        projects = await self.repo.get_all(filters)
        return [ProjectOut.model_validate(p) for p in projects]

    async def get_project(self, project_id: int) -> ProjectOut:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise NotFoundException("Project", project_id)
        return ProjectOut.model_validate(project)

    async def create_project(self, data: ProjectCreate) -> ProjectOut:
        project = await self.repo.create(data.model_dump())
        return ProjectOut.model_validate(project)

    async def update_project(self, project_id: int, data: ProjectUpdate) -> ProjectOut:
        project = await self.repo.update(project_id, data.model_dump(exclude_unset=True))
        if not project:
            raise NotFoundException("Project", project_id)
        return ProjectOut.model_validate(project)

    async def change_status(self, project_id: int, status: str) -> ProjectOut:
        project = await self.repo.update(project_id, {"status": status})
        if not project:
            raise NotFoundException("Project", project_id)
        return ProjectOut.model_validate(project)

    async def delete_project(self, project_id: int) -> None:
        deleted = await self.repo.delete(project_id)
        if not deleted:
            raise NotFoundException("Project", project_id)

    async def get_indicators(self) -> dict:
        projects = await self.repo.get_all()
        total = len(projects)
        active = sum(1 for p in projects if p.status == "active")
        completed = sum(1 for p in projects if p.status == "completed")
        return {
            "total": total,
            "activos": active,
            "completados": completed,
            "enProgreso": total - active - completed,
        }
