"""Skills service - Business logic."""

from shared.exceptions import NotFoundException
from services.skills.repository import SkillRepository
from services.skills.schemas import SkillCreate, SkillUpdate, SkillOut


class SkillService:
    def __init__(self, repo: SkillRepository):
        self.repo = repo

    async def list_skills(self, filters: dict | None = None) -> list[SkillOut]:
        skills = await self.repo.get_all(filters)
        return [SkillOut.model_validate(s) for s in skills]

    async def get_skill(self, skill_id: int) -> SkillOut:
        skill = await self.repo.get_by_id(skill_id)
        if not skill:
            raise NotFoundException("Skill", skill_id)
        return SkillOut.model_validate(skill)

    async def create_skill(self, data: SkillCreate) -> SkillOut:
        skill = await self.repo.create(data.model_dump())
        return SkillOut.model_validate(skill)

    async def update_skill(self, skill_id: int, data: SkillUpdate) -> SkillOut:
        skill = await self.repo.update(skill_id, data.model_dump(exclude_unset=True))
        if not skill:
            raise NotFoundException("Skill", skill_id)
        return SkillOut.model_validate(skill)

    async def delete_skill(self, skill_id: int) -> None:
        deleted = await self.repo.delete(skill_id)
        if not deleted:
            raise NotFoundException("Skill", skill_id)
