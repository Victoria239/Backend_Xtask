"""KPIs service - Database repository."""

from services.kpis.models import Kpi
from shared.repository import BaseRepository


class KpiRepository(BaseRepository[Kpi]):
    model = Kpi
