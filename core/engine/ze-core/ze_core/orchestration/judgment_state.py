"""Bounded System One state shared by ``embed_route`` and ``match_skills``."""

from __future__ import annotations

import time

from ze_core.orchestration.state import AgentState
from ze_core.routing.judge import build_state

HISTORY_HINT_TURNS = 4  # last N messages included as routing context
HISTORY_HINT_CHARS = 240  # per-message truncation
HISTORY_INACTIVITY_MINUTES = 30  # mirror fetch_context's session expiry default


def history_hint(state: AgentState) -> str | None:
    """Compact tail of the conversation so anaphoric follow-ups
    ("are these recent?", "how did you get those?") route to the agent
    that produced the content being referenced."""
    messages = state.get("messages") or []
    if not messages:
        return None

    last_active = state.get("last_active_at")
    if last_active and (time.time() - last_active) > HISTORY_INACTIVITY_MINUTES * 60:
        return None

    lines = []
    for msg in messages[-HISTORY_HINT_TURNS:]:
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{msg.get('role', '?')}: {content[:HISTORY_HINT_CHARS]}")
    if not lines:
        return None
    return "[Recent conversation]\n" + "\n".join(lines)


def build_judgment_state(state: AgentState) -> dict[str, str]:
    """``{user, history?, context?}`` — user text, history hint, routing hints, each capped."""
    return build_state(
        user=state.get("image_caption") or state["prompt"],
        history=history_hint(state),
        context=state.get("routing_hints"),
    )
