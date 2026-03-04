"""Projects service - Business logic."""

from shared.exceptions import NotFoundException
from shared.schemas import PaginatedResponse
from services.projects.repository import ProjectRepository
from services.projects.schemas import ProjectCreate, ProjectUpdate, ProjectOut


class ProjectService:
    def __init__(self, repo: ProjectRepository):
        self.repo = repo

    async def list_projects_paginated(
        self, filters: dict | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        items, total = await self.repo.get_paginated(page, page_size, filters)
        return PaginatedResponse.create(
            items=[ProjectOut.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
        )

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
        return await self.repo.get_indicators()
