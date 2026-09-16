from __future__ import annotations

import json
import re
from typing import Any

from ze_agents.types import ToolCall

COULD_NOT_CANCEL = "I could not cancel that."
COULD_NOT_CLOSE = "I could not close that."
COULD_NOT_ABANDON = "I could not abandon that."


def tool_payload(result: Any) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def flatten_tool_calls(tool_calls: list[ToolCall]) -> list[ToolCall]:
    out: list[ToolCall] = []
    stack = list(tool_calls)
    while stack:
        call = stack.pop(0)
        out.append(call)
        payload = tool_payload(call.result)
        if not payload:
            continue
        nested = payload.get("tool_calls")
        if not isinstance(nested, list):
            continue
        for item in nested:
            if isinstance(item, ToolCall):
                stack.append(item)
            elif isinstance(item, dict):
                stack.append(
                    ToolCall(
                        tool_name=str(item.get("tool_name") or ""),
                        args=item.get("args") or {},
                        result=item.get("result"),
                        duration_ms=int(item.get("duration_ms") or 0),
                        success=bool(item.get("success")),
                        error=item.get("error"),
                    )
                )
    return out


def cancel_reminder_earned(tool_calls: list[ToolCall]) -> bool:
    for call in flatten_tool_calls(tool_calls):
        if call.tool_name != "cancel_reminder":
            continue
        payload = tool_payload(call.result)
        if payload is None:
            continue
        if payload.get("error"):
            continue
        if "cancelled" in payload:
            return True
    return False


def abandon_goal_earned(tool_calls: list[ToolCall]) -> bool:
    for call in flatten_tool_calls(tool_calls):
        if call.tool_name != "abandon_goal":
            continue
        payload = tool_payload(call.result)
        if payload is None:
            continue
        if payload.get("error"):
            continue
        if payload.get("status") == "abandoned":
            return True
    return False


def loop_review_earned(tool_calls: list[ToolCall]) -> bool:
    for call in flatten_tool_calls(tool_calls):
        if call.tool_name not in {"close_loop", "drop_loop"}:
            continue
        payload = tool_payload(call.result)
        if payload is None:
            continue
        if payload.get("error"):
            continue
        state = str(payload.get("state") or "").lower()
        if call.tool_name == "close_loop" and state == "closed":
            return True
        if call.tool_name == "drop_loop" and state == "dropped":
            return True
    return False


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CANCEL_CLAIM = re.compile(
    r"("
    r"i['’]ve cancelled|"
    r"i have cancelled|"
    r"i cancelled|"
    r"cancelled the|"
    r"canceled the|"
    r"cancelled:|"
    r"canceled:"
    r"canceled your reminder|"
    r"reminder (is |was )?cancelled|"
    r"reminder (is |was )?canceled"
    r")",
    re.IGNORECASE,
)
_CLOSE_CLAIM = re.compile(
    r"("
    r"closed the loop|"
    r"loop is closed|"
    r"dropped the (loop|concern)|"
    r"i['’]ve (closed|dropped) (the )?(loop|concern)"
    r")",
    re.IGNORECASE,
)
_ABANDON_CLAIM = re.compile(
    r"("
    r"abandoned (the |your )?goal|"
    r"goal is abandoned|"
    r"i['’]ve abandoned"
    r")",
    re.IGNORECASE,
)
_FORGET_CLAIM = re.compile(
    r"("
    r"i['’]ve forgotten|"
    r"i have forgotten|"
    r"forgotten that|"
    r"i forgot|"
    r"\bwiped\b|"
    r"j[áa] esqueci"
    r")",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return [p.strip() for p in _SENTENCE_SPLIT.split(stripped) if p.strip()]


def enforce_domain_cancel_confirmations(
    response: str,
    tool_calls: list[ToolCall],
) -> str:
    calls = flatten_tool_calls(tool_calls)
    earned_cancel = cancel_reminder_earned(calls)
    earned_close = loop_review_earned(calls)
    earned_abandon = abandon_goal_earned(calls)
    stripped_cancel = False
    stripped_close = False
    stripped_abandon = False
    stripped_forget = False
    kept: list[str] = []
    for sentence in _split_sentences(response):
        drop_cancel = _CANCEL_CLAIM.search(sentence) is not None and not earned_cancel
        drop_close = _CLOSE_CLAIM.search(sentence) is not None and not earned_close
        drop_abandon = (
            _ABANDON_CLAIM.search(sentence) is not None and not earned_abandon
        )
        drop_forget = _FORGET_CLAIM.search(sentence) is not None
        mixed = (
            (earned_cancel or earned_close or earned_abandon)
            and drop_forget
            and (
                _CANCEL_CLAIM.search(sentence)
                or _CLOSE_CLAIM.search(sentence)
                or _ABANDON_CLAIM.search(sentence)
            )
        )
        if mixed:
            drop_cancel = True
            drop_close = True
            drop_abandon = True
        if drop_cancel or drop_close or drop_abandon or drop_forget:
            if drop_cancel:
                stripped_cancel = True
            if drop_close:
                stripped_close = True
            if drop_abandon:
                stripped_abandon = True
            if drop_forget:
                stripped_forget = True
            continue
        kept.append(sentence)
    remainder = " ".join(kept).strip()
    if remainder:
        return remainder
    if stripped_forget and not (stripped_cancel or stripped_close or stripped_abandon):
        return COULD_NOT_CANCEL
    if stripped_cancel:
        return COULD_NOT_CANCEL
    if stripped_close:
        return COULD_NOT_CLOSE
    if stripped_abandon:
        return COULD_NOT_ABANDON
    if stripped_forget:
        return COULD_NOT_CANCEL
    return response
