"""Dashboard service - Database repository."""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from services.dashboard.models import DashboardLayout, DashboardWidget


class LayoutRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_by_user(self, user_id: int) -> list[DashboardLayout]:
        result = await self.db.execute(
            select(DashboardLayout).where(DashboardLayout.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, layout_id: int) -> DashboardLayout | None:
        result = await self.db.execute(
            select(DashboardLayout).where(DashboardLayout.id == layout_id)
        )
        return result.scalar_one_or_none()

    async def get_default(self, user_id: int) -> DashboardLayout | None:
        result = await self.db.execute(
            select(DashboardLayout).where(
                DashboardLayout.user_id == user_id,
                DashboardLayout.is_default == True,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> DashboardLayout:
        layout = DashboardLayout(**data)
        self.db.add(layout)
        await self.db.flush()
        await self.db.refresh(layout)
        return layout

    async def update(self, layout_id: int, data: dict) -> DashboardLayout | None:
        layout = await self.get_by_id(layout_id)
        if not layout:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(layout, key, value)
        await self.db.flush()
        await self.db.refresh(layout)
        return layout

    async def set_default(self, user_id: int, layout_id: int) -> DashboardLayout | None:
        # Unset all defaults for this user
        layouts = await self.get_all_by_user(user_id)
        for layout in layouts:
            layout.is_default = False
        # Set the chosen one
        layout = await self.get_by_id(layout_id)
        if not layout:
            return None
        layout.is_default = True
        await self.db.flush()
        await self.db.refresh(layout)
        return layout

    async def delete(self, layout_id: int) -> bool:
        layout = await self.get_by_id(layout_id)
        if not layout:
            return False
        # Delete widgets first
        await self.db.execute(
            delete(DashboardWidget).where(DashboardWidget.layout_id == layout_id)
        )
        await self.db.delete(layout)
        await self.db.flush()
        return True


class WidgetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_by_layout(self, layout_id: int) -> list[DashboardWidget]:
        result = await self.db.execute(
            select(DashboardWidget).where(DashboardWidget.layout_id == layout_id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, widget_id: int) -> DashboardWidget | None:
        result = await self.db.execute(
            select(DashboardWidget).where(DashboardWidget.id == widget_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> DashboardWidget:
        widget = DashboardWidget(**data)
        self.db.add(widget)
        await self.db.flush()
        await self.db.refresh(widget)
        return widget

    async def update(self, widget_id: int, data: dict) -> DashboardWidget | None:
        widget = await self.get_by_id(widget_id)
        if not widget:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(widget, key, value)
        await self.db.flush()
        await self.db.refresh(widget)
        return widget

    async def delete(self, widget_id: int) -> bool:
        widget = await self.get_by_id(widget_id)
        if not widget:
            return False
        await self.db.delete(widget)
        await self.db.flush()
        return True
