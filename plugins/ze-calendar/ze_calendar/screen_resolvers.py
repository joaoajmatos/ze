"""Screen resolver for reminders (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_sdk.screen import (
    ResolveContext,
    ScreenLine,
    ScreenPosture,
    ScreenRef,
    ScreenResolver,
    as_utc,
    parse_uuid,
    resolve_each,
    sanitize_text,
    time_ago,
)


class ReminderScreenResolver:
    kinds = frozenset({"reminder"})

    def __init__(self, reminder_store: Any) -> None:
        self._reminders = reminder_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref: ScreenRef, ctx: ResolveContext) -> ScreenLine | None:
        reminder_id = parse_uuid(ref.id)
        reminder = await self._reminders.get(reminder_id) if reminder_id else None
        if reminder is None:
            return None
        fire_at = as_utc(reminder.fire_at)
        when = (
            f"fired {time_ago(fire_at, ctx.now)}"
            if reminder.sent
            else f"fires {fire_at:%Y-%m-%d %H:%M} UTC"
        )
        return ScreenLine(
            ref=ref,
            label=sanitize_text(reminder.label, 120),
            summary=when,
            posture=ScreenPosture(
                source="reminder",
                updated_at=as_utc(reminder.sent_at or reminder.created_at),
            ),
        )


def build_screen_resolvers(*, reminder_store: Any) -> list[ScreenResolver]:
    return [ReminderScreenResolver(reminder_store)]
