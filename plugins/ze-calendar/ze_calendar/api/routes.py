from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ze_calendar.api.schemas import PluginPageResponse
from ze_calendar.ui.page import build_reminders_page
from ze_sdk.api import require_api_key

router = APIRouter(
    prefix="/api/v0", tags=["reminders"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "/reminders/page",
    response_model=PluginPageResponse,
    operation_id="getRemindersPage",
    summary="Reminders overview page",
    description="Returns the server-driven UI tree for the reminders management screen.",
)
async def get_reminders_page(request: Request) -> PluginPageResponse:
    store = request.app.state.container._plugin_stores.get("reminder_store")
    if store is None:
        return PluginPageResponse(title="Upcoming", tree=build_reminders_page([]))

    reminders = await store.list_all()
    return PluginPageResponse(
        title="Upcoming",
        tree=build_reminders_page(reminders),
    )
