"""Dashboard service - Business logic."""

from shared.exceptions import NotFoundException
from services.dashboard.repository import LayoutRepository, WidgetRepository
from services.dashboard.schemas import (
    LayoutCreate, LayoutUpdate, LayoutOut,
    WidgetCreate, WidgetUpdate, WidgetOut, WidgetPositionUpdate,
)


class DashboardService:
    def __init__(self, layout_repo: LayoutRepository, widget_repo: WidgetRepository):
        self.layout_repo = layout_repo
        self.widget_repo = widget_repo

    # ─── Layouts ────────────────────────────────────────────

    async def list_layouts(self, user_id: int) -> list[LayoutOut]:
        layouts = await self.layout_repo.get_all_by_user(user_id)
        return [LayoutOut.model_validate(l) for l in layouts]

    async def get_layout(self, layout_id: int) -> LayoutOut:
        layout = await self.layout_repo.get_by_id(layout_id)
        if not layout:
            raise NotFoundException("Layout", layout_id)
        return LayoutOut.model_validate(layout)

    async def get_default_layout(self, user_id: int) -> LayoutOut | None:
        layout = await self.layout_repo.get_default(user_id)
        if not layout:
            return None
        return LayoutOut.model_validate(layout)

    async def create_layout(self, user_id: int, data: LayoutCreate) -> LayoutOut:
        layout_data = data.model_dump()
        layout_data["user_id"] = user_id
        layout = await self.layout_repo.create(layout_data)
        return LayoutOut.model_validate(layout)

    async def update_layout(self, layout_id: int, data: LayoutUpdate) -> LayoutOut:
        layout = await self.layout_repo.update(layout_id, data.model_dump(exclude_unset=True))
        if not layout:
            raise NotFoundException("Layout", layout_id)
        return LayoutOut.model_validate(layout)

    async def set_default(self, user_id: int, layout_id: int) -> LayoutOut:
        layout = await self.layout_repo.set_default(user_id, layout_id)
        if not layout:
            raise NotFoundException("Layout", layout_id)
        return LayoutOut.model_validate(layout)

    async def delete_layout(self, layout_id: int) -> None:
        deleted = await self.layout_repo.delete(layout_id)
        if not deleted:
            raise NotFoundException("Layout", layout_id)

    # ─── Widgets ────────────────────────────────────────────

    async def list_widgets(self, layout_id: int) -> list[WidgetOut]:
        widgets = await self.widget_repo.get_all_by_layout(layout_id)
        return [WidgetOut.model_validate(w) for w in widgets]

    async def add_widget(self, layout_id: int, data: WidgetCreate) -> WidgetOut:
        layout = await self.layout_repo.get_by_id(layout_id)
        if not layout:
            raise NotFoundException("Layout", layout_id)
        widget_data = data.model_dump()
        widget_data["layout_id"] = layout_id
        widget = await self.widget_repo.create(widget_data)
        return WidgetOut.model_validate(widget)

    async def update_widget(self, widget_id: int, data: WidgetUpdate) -> WidgetOut:
        widget = await self.widget_repo.update(widget_id, data.model_dump(exclude_unset=True))
        if not widget:
            raise NotFoundException("Widget", widget_id)
        return WidgetOut.model_validate(widget)

    async def remove_widget(self, widget_id: int) -> None:
        deleted = await self.widget_repo.delete(widget_id)
        if not deleted:
            raise NotFoundException("Widget", widget_id)

    async def update_positions(self, layout_id: int, positions: list[WidgetPositionUpdate]) -> list[WidgetOut]:
        for pos in positions:
            await self.widget_repo.update(pos.id, {"position_x": pos.position_x, "position_y": pos.position_y})
        widgets = await self.widget_repo.get_all_by_layout(layout_id)
        return [WidgetOut.model_validate(w) for w in widgets]
