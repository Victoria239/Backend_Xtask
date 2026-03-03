"""Dashboard service - Database repository."""

from sqlalchemy import select, delete as sa_delete

from services.dashboard.models import DashboardLayout, DashboardWidget
from shared.repository import BaseRepository


class LayoutRepository(BaseRepository[DashboardLayout]):
    model = DashboardLayout

    async def get_all_by_user(self, user_id: int) -> list[DashboardLayout]:
        result = await self.db.execute(
            select(DashboardLayout).where(DashboardLayout.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_default(self, user_id: int) -> DashboardLayout | None:
        result = await self.db.execute(
            select(DashboardLayout).where(
                DashboardLayout.user_id == user_id,
                DashboardLayout.is_default == True,
            )
        )
        return result.scalar_one_or_none()

    async def set_default(self, user_id: int, layout_id: int) -> DashboardLayout | None:
        layouts = await self.get_all_by_user(user_id)
        for layout in layouts:
            layout.is_default = False
        layout = await self.get_by_id(layout_id)
        if not layout:
            return None
        layout.is_default = True
        await self.db.flush()
        await self.db.refresh(layout)
        return layout

    async def delete(self, entity_id: int) -> bool:
        """Override to cascade-delete widgets."""
        layout = await self.get_by_id(entity_id)
        if not layout:
            return False
        await self.db.execute(
            sa_delete(DashboardWidget).where(DashboardWidget.layout_id == entity_id)
        )
        await self.db.delete(layout)
        await self.db.flush()
        return True


class WidgetRepository(BaseRepository[DashboardWidget]):
    model = DashboardWidget

    async def get_all_by_layout(self, layout_id: int) -> list[DashboardWidget]:
        result = await self.db.execute(
            select(DashboardWidget).where(DashboardWidget.layout_id == layout_id)
        )
        return list(result.scalars().all())
