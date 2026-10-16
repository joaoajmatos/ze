from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from ze_core.conversation.messages.types import Message, MessageTrace, ToolCallTrace

_WORKSPACE_RUN_TOOLS = frozenset({"workspace_run", "workspace_run_skill_script"})
_MAX_PHRASES = 3
_NEVER_RAN = ("denied", "refused", "expired", "parked", "refused_over_cap")


class RetryReason(StrEnum):
    NOT_LATEST = "not_latest"
    HAS_WRITE_ACTION = "has_write_action"
    HAS_REVERSIBLE_ACTION = "has_reversible_action"
    HAS_IRREVERSIBLE_ACTION = "has_irreversible_action"
    CONFIRMED_ACTION = "confirmed_action"
    WORKSPACE_RUN = "workspace_run"
    TRACE_UNAVAILABLE = "trace_unavailable"
    UNKNOWN_TOOL = "unknown_tool"
    TURN_PENDING = "turn_pending"
    BUSY = "busy"
    DISCONNECTED = "disconnected"  # client-side only; the server never returns it


@dataclass(frozen=True)
class RetryEligibility:
    available: bool
    reason_code: RetryReason | None = None
    reason_text: str | None = None
    actions: list[str] = field(default_factory=list)
    # False for messages that get no Retry control at all (user messages).
    applicable: bool = True


def retry_eligibility(
    message: Message,
    trace: MessageTrace | None,
    *,
    latest_assistant_id: UUID | None,
    thread_busy: bool = False,
    pending: bool = False,
) -> RetryEligibility:
    """Decide on the server whether regenerating `message` can repeat a side effect.

    Unknown never means safe: a missing trace, an old trace, or a tool the registry did
    not know all make Retry unavailable.
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

    actions = [c for c in trace.tool_calls if _is_action(c)]
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
    if any(c.gate in ("approved", "pre_approved") for c in actions):
        return _no(
            RetryReason.CONFIRMED_ACTION,
            f"{said} You approved it, and Retry never repeats an approved action.",
            phrases,
        )
    if any(c.reversibility == "irreversible" for c in actions):
        return _no(
            RetryReason.HAS_IRREVERSIBLE_ACTION,
            f"{said} That cannot be undone, so Retry would risk repeating it.",
            phrases,
        )
    if all(c.reversibility == "reversible" for c in actions):
        return _no(
            RetryReason.HAS_REVERSIBLE_ACTION,
            f"{said} It can be undone separately, but Retry does not undo actions.",
            phrases,
        )
    return _no(
        RetryReason.HAS_WRITE_ACTION,
        f"{said} Retry never repeats an action.",
        phrases,
    )


def _no(
    code: RetryReason, text: str, actions: list[str] | None = None
) -> RetryEligibility:
    return RetryEligibility(
        available=False, reason_code=code, reason_text=text, actions=actions or []
    )


def _is_action(call: ToolCallTrace) -> bool:
    """A write that ran or may have partly run. A denied or expired gate never ran."""
    return call.access == "write" and call.gate not in _NEVER_RAN


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
    }
