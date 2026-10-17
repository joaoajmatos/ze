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


# Notification target types that name a screen kind under another word. Every other target type
# (episode, insight, goal_suggestion, chat threads) has no resolver, so the hop is dropped
# instead of emitting a "could not load" line for a record nobody looked up.
TARGET_KIND = {
    "open_loop": "loop",
    "person": "contact",
    "project": "entity",
    "entity": "entity",
    "fact": "fact",
    "goal": "goal",
    "goal_gate": "goal_gate",
    "hypothesis": "hypothesis",
    "reminder": "reminder",
    "workspace_run": "workspace_run",
    "held_write": "held_write",
    "workflow": "workflow",
    "workflow_execution": "workflow_execution",
}


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
        kind = TARGET_KIND.get(row.target_type or "")
        target = (
            ScreenRef(kind=kind, id=row.target_id, parent_id=row.target_parent_id)
            if kind and row.target_id
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
