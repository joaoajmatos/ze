from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ze_calendar.api.schemas import PluginPageResponse, ReminderItem
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


@router.get(
    "/reminders",
    response_model=list[ReminderItem],
    operation_id="listReminders",
    summary="List reminders",
    description=(
        "Reminders the user set. status upcoming is unsent and still in the future; "
        "overdue is unsent with a time that has passed (missed while Ze was down); "
        "fired is sent; all is every reminder. Timestamps carry a UTC offset. Returns 503 when the reminder store is not available."
    ),
)
async def list_reminders(
    request: Request,
    status: Literal["upcoming", "overdue", "fired", "all"] = "upcoming",
    limit: int = Query(default=50),
) -> list[ReminderItem]:
    store = request.app.state.container._plugin_stores.get("reminder_store")
    if store is None:
        raise HTTPException(status_code=503, detail="Reminders unavailable")
    rows = await store.list_by_status(status, max(1, min(limit, 200)))
    return [
        ReminderItem(
            id=str(reminder.id),
            label=reminder.label,
            fire_at=reminder.fire_at,
            sent_at=reminder.sent_at,
            status="fired" if reminder.sent else "overdue" if due else "upcoming",
        )
        for reminder, due in rows
    ]
