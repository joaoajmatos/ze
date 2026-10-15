from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from ze_core.conversation.messages.types import (
    Message,
    MessageTrace,
    RollbackRecord,
    ToolCallTrace,
)

_WORKSPACE_RUN_TOOLS = frozenset({"workspace_run", "workspace_run_skill_script"})
_MAX_PHRASES = 3


class RetryReason(StrEnum):
    NOT_LATEST = "not_latest"
    NOT_UNDOABLE = "not_undoable"
    UNDO_FAILED = "undo_failed"
    HAS_IRREVERSIBLE_ACTION = "has_irreversible_action"
    CONFIRMED_ACTION = "confirmed_action"
    WORKSPACE_RUN = "workspace_run"
    TRACE_UNAVAILABLE = "trace_unavailable"
    UNKNOWN_TOOL = "unknown_tool"
    TURN_PENDING = "turn_pending"
    BUSY = "busy"
    DISCONNECTED = "disconnected"  # client-side only; the server never returns it


@dataclass(frozen=True)
class UndoPlanEntry:
    """One undo a Retry will run. `agent` and `undo_args` never leave the server."""

    entry_id: str
    call_index: int
    tool: str
    undo_tool: str
    agent: str
    effect_phrase: str
    undo_note: str
    undo_args: dict[str, Any]


@dataclass(frozen=True)
class RetryEligibility:
    available: bool
    reason_code: RetryReason | None = None
    reason_text: str | None = None
    actions: list[str] = field(default_factory=list)
    # False for messages that get no Retry control at all (user messages).
    applicable: bool = True
    # Reverse call order; empty for a text-only retry or when unavailable.
    plan: list[UndoPlanEntry] = field(default_factory=list)


def retry_eligibility(
    message: Message,
    trace: MessageTrace | None,
    *,
    latest_assistant_id: UUID | None,
    thread_busy: bool = False,
    pending: bool = False,
    rollback: RollbackRecord | None = None,
) -> RetryEligibility:
    """Decide on the server whether regenerating `message` is safe, and what it undoes.

    Unknown never means safe: a missing trace, an old trace, a tool the registry did
    not know, or a reversible action without an undo payload all make Retry unavailable.
    `rollback` is the message's stored record: undone calls drop out of the plan.
    """
    if message.role != "assistant":
        return RetryEligibility(available=False, applicable=False)
    if pending:
        return _no(
            RetryReason.TURN_PENDING, "This turn is waiting for your confirmation."
        )
    if latest_assistant_id is None or message.id != latest_assistant_id:
        return _no(
            RetryReason.NOT_LATEST,
            "Only the latest reply in a conversation can be retried.",
        )
    if thread_busy:
        return _no(RetryReason.BUSY, "Ze is already working on this conversation.")
    if trace is None:
        return _no(
            RetryReason.TRACE_UNAVAILABLE,
            "Ze has no record of what this reply did, so it cannot tell if a retry is safe.",
        )
    if not trace.effects_known or any(c.access == "unknown" for c in trace.tool_calls):
        return _no(
            RetryReason.UNKNOWN_TOOL,
            "Ze cannot tell what this reply did, so it cannot tell if a retry is safe.",
        )

    failed = (
        next((e for e in rollback.entries if e.outcome == "failed"), None)
        if rollback
        else None
    )
    if failed is not None:
        undone = _said_undone(rollback)
        return _no(
            RetryReason.UNDO_FAILED,
            f"{undone}Ze could not undo: {failed.effect_phrase}. Retry stays off so nothing is repeated.",
        )
    done = (
        {e.call_index for e in rollback.entries if e.outcome == "undone"}
        if rollback
        else set()
    )
    actions = [
        c for c in trace.tool_calls if _is_action(c) and c.call_index not in done
    ]
    phrases = _phrases(actions)
    said = _said(phrases)

    if _ran_workspace(trace, actions):
        return _no(
            RetryReason.WORKSPACE_RUN,
            f"{said} Workspace commands cannot be undone, so Retry would risk repeating them.",
            phrases,
        )
    if not actions:
        return RetryEligibility(available=True)
    irreversible = [c for c in actions if c.reversibility != "reversible"]
    if irreversible:
        if any(c.gate == "approved" for c in irreversible):
            return _no(
                RetryReason.CONFIRMED_ACTION,
                f"{said} You approved it, and Retry never repeats an approved action.",
                phrases,
            )
        return _no(
            RetryReason.HAS_IRREVERSIBLE_ACTION,
            f"{said} That cannot be undone, so Retry would risk repeating it.",
            phrases,
        )
    if any(not _undoable(c) for c in actions):
        return _no(
            RetryReason.NOT_UNDOABLE,
            f"{said} That cannot be undone cleanly this time, so Retry would risk repeating it.",
            phrases,
        )
    plan = [
        _plan_entry(message, c)
        for c in sorted(actions, key=lambda c: c.call_index, reverse=True)
    ]
    return RetryEligibility(available=True, actions=phrases, plan=plan)


def _undoable(call: ToolCallTrace) -> bool:
    return bool(
        call.success and call.undo_args is not None and call.undo_tool and call.agent
    )


def _entry_id(message_id: UUID, call: ToolCallTrace) -> str:
    canonical = json.dumps(call.undo_args, sort_keys=True, separators=(",", ":"))
    raw = f"{message_id}:{call.call_index}:{call.name}:{canonical}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _plan_entry(message: Message, call: ToolCallTrace) -> UndoPlanEntry:
    return UndoPlanEntry(
        entry_id=_entry_id(message.id, call),
        call_index=call.call_index,
        tool=call.name,
        undo_tool=call.undo_tool or "",
        agent=call.agent or "",
        effect_phrase=_phrase(call),
        undo_note=call.undo_note or "",
        undo_args=dict(call.undo_args or {}),
    )


def _said_undone(rollback: RollbackRecord | None) -> str:
    if rollback is None:
        return ""
    done = [e.effect_phrase for e in rollback.entries if e.outcome == "undone"]
    if not done:
        return ""
    return f"Ze undid: {', '.join(done)}. "


def _no(
    code: RetryReason, text: str, actions: list[str] | None = None
) -> RetryEligibility:
    return RetryEligibility(
        available=False, reason_code=code, reason_text=text, actions=actions or []
    )


def _is_action(call: ToolCallTrace) -> bool:
    """A write that ran or may have partly run. A denied or expired gate never ran."""
    return call.access == "write" and call.gate not in ("denied", "expired")


def _ran_workspace(trace: MessageTrace, actions: list[ToolCallTrace]) -> bool:
    """A denied or expired workspace run never started, so it does not count."""
    run_calls = [c for c in trace.tool_calls if c.name in _WORKSPACE_RUN_TOOLS]
    if run_calls:
        return any(_is_action(c) for c in run_calls)
    return trace.workspace is not None and bool(trace.workspace.runs)


def _phrase(call: ToolCallTrace) -> str:
    return call.effect_phrase or f"ran {call.name.replace('_', ' ')}"


def _phrases(actions: list[ToolCallTrace]) -> list[str]:
    seen: list[str] = []
    for call in actions:
        phrase = _phrase(call)
        if phrase not in seen:
            seen.append(phrase)
    return seen[:_MAX_PHRASES]


def _said(phrases: list[str]) -> str:
    if not phrases:
        return "This reply took an action."
    if len(phrases) == 1:
        joined = phrases[0]
    else:
        joined = ", ".join(phrases[:-1]) + f" and {phrases[-1]}"
    return f"This reply {joined}."


def eligibility_payload(result: RetryEligibility) -> dict[str, Any]:
    return {
        "available": result.available,
        "reason_code": result.reason_code.value if result.reason_code else None,
        "reason_text": result.reason_text,
        "plan": [
            {
                "entry_id": e.entry_id,
                "tool": e.tool,
                "effect_phrase": e.effect_phrase,
                "undo_note": e.undo_note,
            }
            for e in result.plan
        ],
    }
