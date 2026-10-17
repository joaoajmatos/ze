"""
LLM-as-judge for Ze eval responses.

Called when --judge flag is set. Scores each scenario response on quality,
tone, and tool_use dimensions using an OpenRouter-hosted model.

The judge() function signature is the stable public interface. The internal
implementation can be swapped for DeepEval's GEval in a follow-up phase
without changing any callers — only this module changes.
"""

from __future__ import annotations

import json
import os
from datetime import date

import httpx

from ze_eval.types import JudgeScore

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_JUDGE_MODEL = "anthropic/claude-haiku-4-5"

_SYSTEM = (
    "You are an evaluation judge for Ze, a personal AI assistant. "
    "Your job is to assess Ze's response given a set of criteria. "
    "Respond with valid JSON only — no prose, no markdown fences."
)

_PROMPT = """\
## Scenario
{description}

## User message
{prompt}

## Ze's response
{response}

## Routing
Expected agent: {expected_agent}
Actual agent used: {agent_used}

## What Ze did (from the trace)
Today's date: {today}. Your own knowledge may be older; do not mark a date or version wrong only because you do not know it.
Tool calls:
{tool_calls}
Components shown to the user below the reply:
{components}
Waiting for the user's confirmation: {pending_confirmation}
Notes: a call marked "parked" waits for the user's approval; it counts as invoking the tool. A call marked "denied", "refused", "expired" or "refused_over_cap" did not run. A call marked "ok (approved)" ran after the user approved it. A call prefixed "[turn N]" was made during turn N of a multi-turn scenario. A rendered component is a card, table, chart or form the user sees beside the reply; judge its content as part of the answer. Web search runs on the server and never appears in the tool call list.

## Criteria
{criteria}

Score each dimension on a 1–5 scale (1 = completely fails, 5 = excellent).
Return JSON with exactly these fields:
- quality (int 1-5): Does Ze actually answer the question well?
- tone (int 1-5): Is the tone appropriate — warm, direct, in character?
- tool_use (int 1-5 or null): Did Ze use tools correctly? null if no tools expected or invoked.
- pass (bool): Would a real user be satisfied with this response?
- reasoning (str): One or two sentences explaining your scores.
"""


_UNRUN_GATES = frozenset(
    {"parked", "denied", "refused", "expired", "refused_over_cap", "duplicate"}
)
_APPROVED_GATES = frozenset({"approved", "pre_approved"})


def format_tool_calls(tool_calls: list[dict] | None) -> str:
    if not tool_calls:
        return "- none recorded"
    lines = []
    for call in tool_calls:
        gate = call.get("gate") or ("parked" if call.get("parked") else "none")
        if gate in _UNRUN_GATES:
            state = gate
        else:
            state = "ok" if call.get("success", True) else "failed"
            if gate in _APPROVED_GATES and state == "ok":
                state = f"ok ({gate})"
        turn = call.get("turn")
        turn_prefix = f"[turn {turn}] " if turn else ""
        lines.append(f"- {turn_prefix}{call.get('tool_name', '?')} ({state})")
    return "\n".join(lines)


_PRESENTATION_KEYS = frozenset(
    {"color", "gap", "style", "variant", "size", "align", "padding", "id"}
)
_COMPONENT_CHARS = 700
_MAX_COMPONENTS = 8


def _strip_presentation(node):
    # Top level only: nested keys such as "color" or "id" are often data fields.
    if isinstance(node, dict):
        return {k: v for k, v in node.items() if k not in _PRESENTATION_KEYS}
    return node


def format_components(components: list[dict] | None) -> str:
    """One line per rendered component: its kind and its data, minus styling."""
    if not components:
        return "- none"
    lines = []
    for component in components[:_MAX_COMPONENTS]:
        turn = component.get("turn") if isinstance(component, dict) else None
        body = component.get("component", component) if turn else component
        kind = body.get("type", "?") if isinstance(body, dict) else "?"
        data = json.dumps(_strip_presentation(body), ensure_ascii=False)
        if len(data) > _COMPONENT_CHARS:
            data = data[:_COMPONENT_CHARS] + "…"
        turn_prefix = f"[turn {turn}] " if turn else ""
        lines.append(f"- {turn_prefix}{kind}: {data}")
    if len(components) > _MAX_COMPONENTS:
        lines.append(f"- … and {len(components) - _MAX_COMPONENTS} more not shown")
    return "\n".join(lines)


def build_prompt(
    *,
    description: str,
    prompt: str,
    response: str,
    expected_agent: str | None,
    agent_used: str | None,
    criteria: list[str],
    tool_calls: list[dict] | None = None,
    components: list[dict] | None = None,
    pending_confirmation: bool = False,
    today: date | None = None,
) -> str:
    return _PROMPT.format(
        description=description,
        prompt=prompt,
        response=response,
        expected_agent=expected_agent or "any",
        agent_used=agent_used or "unknown",
        criteria="\n".join(f"- {c}" for c in criteria),
        tool_calls=format_tool_calls(tool_calls),
        components=format_components(components),
        pending_confirmation="yes" if pending_confirmation else "no",
        today=(today or date.today()).isoformat(),
    )


async def judge(
    *,
    description: str,
    prompt: str,
    response: str,
    expected_agent: str | None,
    agent_used: str | None,
    criteria: list[str],
    tool_calls: list[dict] | None = None,
    components: list[dict] | None = None,
    pending_confirmation: bool = False,
    model: str = DEFAULT_JUDGE_MODEL,
    api_key: str | None = None,
) -> JudgeScore:
    key = api_key or os.environ["OPENROUTER_API_KEY"]
    user_msg = build_prompt(
        description=description,
        prompt=prompt,
        response=response,
        expected_agent=expected_agent,
        agent_used=agent_used,
        criteria=criteria,
        tool_calls=tool_calls,
        components=components,
        pending_confirmation=pending_confirmation,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _OPENROUTER_URL,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.0,
                "max_tokens": 600,
                "response_format": {"type": "json_object"},
            },
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "https://github.com/ze",
                "X-Title": "Ze Eval Judge",
            },
        )
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"].get("content")
    return parse_judge_reply(content, model=model)


class JudgeParseError(ValueError):
    """The judge model's reply could not be turned into a JudgeScore."""


def _extract_json_object(text: str) -> dict:
    """Parse a JSON object from a model reply, tolerating fences and prose.

    Models routinely wrap JSON in ```json fences even when told not to and
    when response_format=json_object is requested (OpenRouter does not enforce
    it for every provider).
    """
    stripped = text.strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start == -1 or end <= start:
            raise
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise JudgeParseError(f"expected a JSON object, got {type(value).__name__}")
    return value


def parse_judge_reply(content: str | None, *, model: str = "") -> JudgeScore:
    snippet = (content or "").strip()[:120]
    if not snippet:
        raise JudgeParseError(f"judge model {model!r} returned an empty reply")
    try:
        parsed = _extract_json_object(content or "")
        return JudgeScore(
            quality=int(parsed["quality"]),
            tone=int(parsed["tone"]),
            tool_use=int(parsed["tool_use"])
            if parsed.get("tool_use") is not None
            else None,
            pass_=bool(parsed["pass"]),
            reasoning=str(parsed["reasoning"]),
        )
    except JudgeParseError:
        raise
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise JudgeParseError(
            f"unusable judge reply from {model!r} ({type(exc).__name__}: {exc}); "
            f"starts with: {snippet!r}"
        ) from exc
