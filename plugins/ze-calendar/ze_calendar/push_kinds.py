from __future__ import annotations

from ze_sdk.proactive import PushKind

USER_REMINDER = PushKind("user_reminder", "requested", "high", "calendar")
CALENDAR_REMINDER = PushKind("calendar_reminder", "requested", "high", "calendar")
CALENDAR_REMINDERS_SCHEDULED = PushKind(
    "calendar_reminders_scheduled", "accountability", "low", "calendar"
)
