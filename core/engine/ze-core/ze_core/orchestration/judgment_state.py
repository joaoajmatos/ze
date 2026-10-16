"""Bounded System One states: routing and skills share one, the tier judge has its own."""

from __future__ import annotations

import time
from typing import Any

from ze_agents.registry import get_enabled_agents

from ze_core.conversation.messages.memory_chunks import extract_memory_chunks
from ze_core.orchestration.state import AgentState
from ze_core.routing.judge import build_state, criterion_for

HISTORY_HINT_TURNS = 4  # last N messages included as routing context
HISTORY_HINT_CHARS = 240  # per-message truncation
HISTORY_INACTIVITY_MINUTES = 30  # mirror fetch_context's session expiry default

TIER_TASK_CAP = 2000
TIER_CONVERSATION_TURNS = 8
TIER_MESSAGE_CAP = 400
TIER_CONVERSATION_CAP = 2400
TIER_RECAP_CAP = 800
TIER_MEMORY_ITEMS = 5
TIER_MEMORY_ITEM_CAP = 200
TIER_FOCUS_CAP = 600
TIER_SKILL_CAP = 300
TIER_AGENT_CAP = 600

_RECAP_HEADER = "[Resuming"
_RECAP_WORKFLOWS = "In-flight workflows:"
_RECAP_OFFERS = "Not yet tracked"


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


def _tier_conversation(ctx: Any) -> str:
    """Last prior turns, oldest dropped first. ``fetch_context`` appends the current
    message as the last entry of ``messages``, so it is not part of the history."""
    messages = list(getattr(ctx, "messages", None) or [])
    if messages and messages[-1].get("role") == "user":
        messages = messages[:-1]
    lines: list[str] = []
    for msg in messages[-TIER_CONVERSATION_TURNS:]:
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{msg.get('role', '?')}: {content[:TIER_MESSAGE_CAP]}")
    kept: list[str] = []
    total = 0
    for line in reversed(lines):
        total += len(line) + (1 if kept else 0)
        if total > TIER_CONVERSATION_CAP:
            break
        kept.append(line)
    return "\n".join(reversed(kept))


def _split_recap(recap: str | None) -> tuple[str, list[str]]:
    """(narrative and open items, in-flight workflow lines); header and offers dropped."""
    main: list[str] = []
    workflows: list[str] = []
    section = "main"
    for line in (recap or "").splitlines():
        if line.startswith(_RECAP_HEADER):
            continue
        if line.startswith(_RECAP_WORKFLOWS):
            section = "workflows"
            continue
        if line.startswith(_RECAP_OFFERS):
            section = "offers"
            continue
        if section == "workflows" and line.startswith("- "):
            workflows.append(line[2:].strip())
        elif section == "main":
            main.append(line)
        elif section == "workflows":
            section = "main"
            main.append(line)
    return "\n".join(main).strip(), workflows


def _tier_memory(memory_context: Any) -> str:
    chunks = sorted(
        extract_memory_chunks(memory_context), key=lambda c: c.score, reverse=True
    )
    return "\n".join(
        f"- {c.text[:TIER_MEMORY_ITEM_CAP]}" for c in chunks[:TIER_MEMORY_ITEMS]
    )


def _tier_focus(state: AgentState, ctx: Any, workflows: list[str]) -> str:
    parts: list[str] = []
    hints = (state.get("routing_hints") or "").strip()
    if hints:
        parts.append(hints)
    note = (getattr(ctx, "screen_context_note", None) or "").strip()
    if note:
        parts.append(note)
    for match in getattr(ctx, "procedure_matches", None) or []:
        name = getattr(match, "name", None)
        if name:
            parts.append(f"Procedure: {name}")
    parts.extend(f"In-flight workflow: {line}" for line in workflows)
    return "\n".join(parts)


def _tier_skill(ctx: Any) -> str:
    lines = []
    for skill in getattr(ctx, "active_skills", None) or []:
        name = getattr(skill, "name", "")
        description = (getattr(skill, "description", "") or "").strip()
        lines.append(f"{name}: {description}" if description else name)
    return "\n".join(lines)


def _tier_agent(state: AgentState) -> str:
    envelope = state.get("envelope")
    if envelope is None:
        return ""
    name = envelope.subtasks[0].agent if envelope.subtasks else envelope.primary_agent
    cls = get_enabled_agents().get(name)
    if cls is None:
        return name
    text = f"{name}: {criterion_for(cls)}"
    tools = [t for t in getattr(cls, "tools", None) or [] if isinstance(t, str)]
    if tools:
        text += f"\nTools: {', '.join(tools)}"
    return text


def build_tier_state(state: AgentState) -> dict[str, str]:
    """``{task, conversation?, recap?, memory?, focus?, skill?, agent?}`` for the tier judge.

    Named, capped fields only; empty ones are omitted (ADR pin 6, research R3).
    """
    ctx = state.get("agent_context")
    recap, workflows = _split_recap(getattr(ctx, "resume_recap", None))
    fields = {
        "task": (state.get("image_caption") or state["prompt"])[:TIER_TASK_CAP],
        "conversation": _tier_conversation(ctx),
        "recap": recap[:TIER_RECAP_CAP],
        "memory": _tier_memory(state.get("memory_context")),
        "focus": _tier_focus(state, ctx, workflows)[:TIER_FOCUS_CAP],
        "skill": _tier_skill(ctx)[:TIER_SKILL_CAP],
        "agent": _tier_agent(state)[:TIER_AGENT_CAP],
    }
    return {key: value for key, value in fields.items() if value.strip()}
