from __future__ import annotations

import json
import re
from typing import Any

from ze_agents.nested_tools import (
    COULD_NOT_ABANDON,
    COULD_NOT_CANCEL,
    COULD_NOT_CLOSE,
    abandon_goal_earned,
    cancel_reminder_earned,
    flatten_tool_calls,
    loop_review_earned,
)
from ze_sdk.types import ToolCall

COULD_NOT_STORE = "I could not store that."
COULD_NOT_FORGET = "I could not forget that."
COULD_NOT_STORE_OR_FORGET = "I could not store or forget that."
COULD_NOT_APPLY_CONSTRAINT = "I could not apply that constraint."

_REMEMBER_CLAIM = re.compile(
    r"("
    r"i['’]ll remember|"
    r"i will remember|"
    r"i['’]ve remembered|"
    r"i have remembered|"
    r"remembered that|"
    r"i['’]ve stored|"
    r"i have stored|"
    r"i['’]ve saved|"
    r"i will store|"
    r"stored that|"
    r"vou lembrar|"
    r"j[áa] me lembrei"
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

_VETO_CLAIM = re.compile(
    r"("
    r"because of your constraint|"
    r"your standing constraint|"
    r"blocked by .{0,40}constraint|"
    r"i['’]ll not (send|schedule|email|mail)|"
    r"i won['’]t (send|schedule|email|mail)|"
    r"i will not (send|schedule|email|mail)"
    r")",
    re.IGNORECASE,
)

_RECITATION_CLAIM = re.compile(
    r"("
    r"i remember that you|"
    r"i remember you|"
    r"as i recall you|"
    r"i recall that you|"
    r"as i remember you|"
    r"lembro-me que voc[eê]|"
    r"eu lembro que voc[eê]"
    r")",
    re.IGNORECASE,
)

_TASK_PARAPHRASE = re.compile(
    r"i remember that you (asked|told|said|wanted me)",
    re.IGNORECASE,
)

_ASKED_RECALL = re.compile(
    r"("
    r"what do you know|"
    r"what do you remember|"
    r"what you know about|"
    r"tell me about me|"
    r"what'?s my|"
    r"whats my|"
    r"what is my|"
    r"do you remember|"
    r"have you remembered|"
    r"where do i|"
    r"where'?s my|"
    r"what do i prefer|"
    r"favourite|"
    r"favorite|"
    r"seating"
    r")",
    re.IGNORECASE,
)

RECITATION_FALLBACK = "Okay."

_MIXED_EXTRA_MEMORY = re.compile(
    r"\balso\b.{0,80}(remember|stored|saved|forgot|forgotten)",
    re.IGNORECASE,
)

_INGEST_FILE_WHOLE = re.compile(
    r"("
    r"\b(this|the|that)\s+(pdf|file|document|video|link|url)\b|"
    r"\bremember.{0,40}\b(pdf|file|document|video)\b|"
    r"\b(pdf|file|document|video).{0,40}\bremember|"
    r"\bingest(ed|ing)?\b.{0,40}\b(remember|stored|saved)\b"
    r")",
    re.IGNORECASE,
)

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

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _tool_payload(result: Any) -> dict[str, Any] | None:
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


def _ok_true(result: Any) -> bool:
    payload = _tool_payload(result)
    return payload is not None and payload.get("ok") is True


def _earned(tool_calls: list[ToolCall], name: str) -> bool:
    return any(call.tool_name == name and _ok_true(call.result) for call in tool_calls)


def _earned_veto(tool_calls: list[ToolCall]) -> bool:
    for call in tool_calls:
        payload = _tool_payload(call.result)
        if payload is not None and payload.get("veto") is True:
            return True
    return False


def _split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    parts = _SENTENCE_SPLIT.split(stripped)
    return [p.strip() for p in parts if p.strip()]


def hold_token_sink(ctx: Any) -> Any:
    original = ctx.token_sink

    async def _buffer(_chunk: str) -> None:
        return None

    if original is not None:
        ctx.token_sink = _buffer
    return original


async def publish_honest_reply(
    original_sink: Any,
    response: str,
    tool_calls: list[ToolCall],
    user_text: str | None = None,
) -> str:
    gated = enforce_memory_confirmations(response, tool_calls, user_text=user_text)
    if original_sink is not None:
        await original_sink(gated)
    return gated


def _asked_recall(user_text: str | None) -> bool:
    if not user_text:
        return False
    return _ASKED_RECALL.search(user_text) is not None


def _in_turn_quote(sentence: str, user_text: str | None) -> bool:
    if not user_text:
        return False
    remainder = _RECITATION_CLAIM.sub("", sentence).strip(" .,'\"")
    if len(remainder) < 8:
        return False
    return remainder.lower() in user_text.lower()


def enforce_memory_confirmations(
    response: str,
    tool_calls: list[ToolCall],
    user_text: str | None = None,
) -> str:
    calls = flatten_tool_calls(tool_calls)
    earned_remember = _earned(calls, "remember_fact")
    earned_forget = _earned(calls, "forget_fact")
    earned_veto = _earned_veto(calls)
    earned_cancel = cancel_reminder_earned(calls)
    earned_close = loop_review_earned(calls)
    earned_abandon = abandon_goal_earned(calls)
    stripped_remember = False
    stripped_forget = False
    stripped_veto = False
    stripped_recitation = False
    stripped_cancel = False
    stripped_close = False
    stripped_abandon = False
    stripped_file_whole = False
    asked_recall = _asked_recall(user_text)
    kept: list[str] = []

    for sentence in _split_sentences(response):
        has_remember = _REMEMBER_CLAIM.search(sentence) is not None
        has_forget = _FORGET_CLAIM.search(sentence) is not None
        has_veto = _VETO_CLAIM.search(sentence) is not None
        has_cancel = _CANCEL_CLAIM.search(sentence) is not None
        has_close = _CLOSE_CLAIM.search(sentence) is not None
        has_abandon = _ABANDON_CLAIM.search(sentence) is not None
        mixed = (
            (earned_remember or earned_forget)
            and (has_remember or has_forget)
            and _MIXED_EXTRA_MEMORY.search(sentence) is not None
        )
        mixed_domain_forget = (
            has_forget
            and not earned_forget
            and (
                (has_cancel and earned_cancel)
                or (has_close and earned_close)
                or (has_abandon and earned_abandon)
            )
        )
        drop_remember = has_remember and (not earned_remember or mixed)
        drop_file_whole = (
            has_remember and _INGEST_FILE_WHOLE.search(sentence) is not None
        )
        if drop_file_whole:
            drop_remember = True
        drop_forget = has_forget and (not earned_forget or mixed)
        drop_veto = has_veto and not earned_veto
        drop_cancel = has_cancel and (not earned_cancel or mixed_domain_forget)
        drop_close = has_close and (not earned_close or mixed_domain_forget)
        drop_abandon = has_abandon and (not earned_abandon or mixed_domain_forget)
        if mixed and has_remember:
            drop_remember = True
        if mixed and has_forget:
            drop_forget = True
        drop_recitation = (
            user_text is not None
            and _RECITATION_CLAIM.search(sentence) is not None
            and not asked_recall
            and _TASK_PARAPHRASE.search(sentence) is None
            and not _in_turn_quote(sentence, user_text)
        )
        if (
            drop_remember
            or drop_forget
            or drop_veto
            or drop_recitation
            or drop_cancel
            or drop_close
            or drop_abandon
        ):
            if drop_remember:
                if drop_file_whole and earned_remember:
                    stripped_file_whole = True
                else:
                    stripped_remember = True
                    if drop_file_whole:
                        stripped_file_whole = True
            if drop_forget:
                stripped_forget = True
            if drop_veto:
                stripped_veto = True
            if drop_cancel:
                stripped_cancel = True
            if drop_close:
                stripped_close = True
            if drop_abandon:
                stripped_abandon = True
            if drop_recitation and not (
                drop_remember
                or drop_forget
                or drop_veto
                or drop_cancel
                or drop_close
                or drop_abandon
            ):
                stripped_recitation = True
            continue
        kept.append(sentence)

    remainder = " ".join(kept).strip()
    if remainder:
        return remainder
    if stripped_remember and stripped_forget:
        return COULD_NOT_STORE_OR_FORGET
    if stripped_forget:
        return COULD_NOT_FORGET
    if stripped_remember:
        return COULD_NOT_STORE
    if stripped_veto:
        return COULD_NOT_APPLY_CONSTRAINT
    if stripped_cancel:
        return COULD_NOT_CANCEL
    if stripped_close:
        return COULD_NOT_CLOSE
    if stripped_abandon:
        return COULD_NOT_ABANDON
    if stripped_recitation or stripped_file_whole:
        return RECITATION_FALLBACK
    return response
