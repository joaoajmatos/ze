from __future__ import annotations

from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException

from ze_api.api.deps import (
    get_interruption_settings_store,
    get_notification_store,
    get_notifier,
    require_api_key,
)
from ze_api.api.schemas import (
    MarkAllReadResponse,
    NotificationItem,
    NotificationListResponse,
    QuietHoursResponse,
    QuietHoursUpdate,
    UnreadCountResponse,
)
from ze_proactive.notification_store import InvalidCursorError
from ze_proactive.quiet_hours import is_active

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "",
    response_model=NotificationListResponse,
    operation_id="listNotifications",
    summary="List notifications",
    description=(
        "Reverse-chronological, cursor-paginated notification history. "
        "Set mark_read=true to atomically mark the returned page as read "
        "(used by the panel-open fetch)."
    ),
)
async def list_notifications(
    cursor: str | None = None,
    limit: int = 20,
    unread_only: bool = False,
    mark_read: bool = False,
    notification_store=Depends(get_notification_store),
) -> NotificationListResponse:
    try:
        items, next_cursor = await notification_store.list_page(
            cursor=cursor,
            limit=limit,
            unread_only=unread_only,
            mark_read=mark_read,
        )
    except InvalidCursorError:
        raise HTTPException(status_code=400, detail="Invalid cursor")

    return NotificationListResponse(
        items=[NotificationItem(**vars(n)) for n in items],
        next_cursor=next_cursor,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    operation_id="getUnreadNotificationCount",
    summary="Get unread notification count",
    description="Returns the number of unread notifications, for the bell badge.",
)
async def get_unread_count(
    notification_store=Depends(get_notification_store),
) -> UnreadCountResponse:
    count = await notification_store.unread_count()
    return UnreadCountResponse(count=count)


def _parse_quiet_time(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


async def _quiet_hours_response(
    setting, notification_store, notifier
) -> QuietHoursResponse:
    return QuietHoursResponse(
        enabled=setting.enabled,
        start=setting.start.strftime("%H:%M") if setting.start else None,
        end=setting.end.strftime("%H:%M") if setting.end else None,
        timezone=setting.timezone,
        active_now=is_active(setting, datetime.now(timezone.utc)),
        held_count=await notification_store.count_held(),
        max_discretionary_per_day=notifier.max_discretionary_per_day,
    )


@router.get(
    "/quiet-hours",
    response_model=QuietHoursResponse,
    operation_id="getQuietHours",
    summary="Get quiet hours",
    description=(
        "The user's quiet-hours setting, whether it is active now, how many pushes "
        "are held, and the daily budget for unprompted pushes."
    ),
)
async def get_quiet_hours(
    settings_store=Depends(get_interruption_settings_store),
    notification_store=Depends(get_notification_store),
    notifier=Depends(get_notifier),
) -> QuietHoursResponse:
    setting = await settings_store.get()
    return await _quiet_hours_response(setting, notification_store, notifier)


@router.put(
    "/quiet-hours",
    response_model=QuietHoursResponse,
    operation_id="updateQuietHours",
    summary="Update quiet hours",
    description=(
        "Save the quiet-hours window. While active, only reminders the user set are "
        "pushed; other pushes are held and released when quiet hours end."
    ),
)
async def update_quiet_hours(
    body: QuietHoursUpdate,
    settings_store=Depends(get_interruption_settings_store),
    notification_store=Depends(get_notification_store),
    notifier=Depends(get_notifier),
) -> QuietHoursResponse:
    setting = await settings_store.upsert(
        body.enabled,
        _parse_quiet_time(body.start),
        _parse_quiet_time(body.end),
        body.timezone,
    )
    return await _quiet_hours_response(setting, notification_store, notifier)


@router.post(
    "/{notification_id}/read",
    status_code=204,
    operation_id="markNotificationRead",
    summary="Mark a notification read",
    description="Marks a single notification read. Idempotent.",
)
async def mark_notification_read(
    notification_id: str,
    notification_store=Depends(get_notification_store),
) -> None:
    found = await notification_store.mark_read(notification_id)
    if not found:
        raise HTTPException(status_code=404, detail="Notification not found")


@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
    operation_id="markAllNotificationsRead",
    summary="Mark all notifications read",
    description="Marks every currently-unread notification read.",
)
async def mark_all_notifications_read(
    notification_store=Depends(get_notification_store),
) -> MarkAllReadResponse:
    marked = await notification_store.mark_all_read()
    return MarkAllReadResponse(marked=marked)
