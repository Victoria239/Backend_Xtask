"""Skills service - Database repository."""

from services.skills.models import Skill
from shared.repository import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    model = Skill
