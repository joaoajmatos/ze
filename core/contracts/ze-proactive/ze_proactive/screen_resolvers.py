"""Screen resolver for notifications (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_agents.screen import (
    ResolveContext,
    ScreenLine,
    ScreenPosture,
    ScreenRef,
    ScreenResolver,
    as_utc,
    resolve_each,
    sanitize_text,
    time_ago,
)


class NotificationScreenResolver:
    kinds = frozenset({"notification"})

    def __init__(self, notification_store: Any) -> None:
        self._notifications = notification_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, lambda ref: self._load(ref, ctx))

    async def _load(self, ref: ScreenRef, ctx: ResolveContext) -> ScreenLine | None:
        row = await self._notifications.get(ref.id)
        if row is None:
            return None
        # The core resolves the target one hop; `parent_id` comes from the row (phase 184).
        target = (
            ScreenRef(
                kind=row.target_type, id=row.target_id, parent_id=row.target_parent_id
            )
            if row.target_type and row.target_id
            else None
        )
        created = as_utc(row.created_at)
        return ScreenLine(
            ref=ref,
            label=sanitize_text(row.title, 120),
            summary=f"notification from {sanitize_text(row.source, 30)}, {time_ago(created, ctx.now)}",
            posture=ScreenPosture(source="notification", updated_at=created),
            target=target,
        )


def build_screen_resolvers(*, notification_store: Any) -> list[ScreenResolver]:
    return [NotificationScreenResolver(notification_store)]
