"""Which agent owns the record a "Chat about this" turn is about (phase 195)."""

from __future__ import annotations

from ze_agents.screen import ScreenContext, ScreenOrigin

DEFAULT_OWNER = "companion"

OWNER_AGENT = {
    "loop": "loops",
    "goal": "goals",
    "goal_gate": "goals",
    "workflow": "workflow",
    "workflow_execution": "workflow",
    "reminder": "reminders",
    "news_article": "news",
}


def screen_owner(ctx: ScreenContext | None, enabled: set[str]) -> str | None:
    """The agent a chat_about turn goes to, or None when routing should run as usual.

    Only a turn the user started with the chip and that has a subject is routed this way. Records
    without a specialist (facts, entities, contacts, skills, notifications, ...) go to companion,
    which reads them with the screen note. An owner that is not enabled falls back to companion.
    """
    if ctx is None or ctx.origin is not ScreenOrigin.CHAT_ABOUT or not ctx.subject:
        return None
    owner = OWNER_AGENT.get(ctx.subject[0].kind, DEFAULT_OWNER)
    if owner in enabled:
        return owner
    return DEFAULT_OWNER if DEFAULT_OWNER in enabled else None
