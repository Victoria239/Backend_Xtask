"""Skills service - Database repository."""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.skills.models import Skill


class SkillRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, filters: dict | None = None) -> list[Skill]:
        query = select(Skill).order_by(desc(Skill.created_at))
        if filters:
            if filters.get("employee_id"):
                query = query.where(Skill.employee_id == filters["employee_id"])
            if filters.get("category"):
                query = query.where(Skill.category == filters["category"])
            if filters.get("level"):
                query = query.where(Skill.level == filters["level"])
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, skill_id: int) -> Skill | None:
        result = await self.db.execute(select(Skill).where(Skill.id == skill_id))
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Skill:
        skill = Skill(**data)
        self.db.add(skill)
        await self.db.flush()
        await self.db.refresh(skill)
        return skill

    async def update(self, skill_id: int, data: dict) -> Skill | None:
        skill = await self.get_by_id(skill_id)
        if not skill:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(skill, key, value)
        await self.db.flush()
        await self.db.refresh(skill)
        return skill

    async def delete(self, skill_id: int) -> bool:
        skill = await self.get_by_id(skill_id)
        if not skill:
            return False
        await self.db.delete(skill)
        await self.db.flush()
        return True
