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


async def judge(
    *,
    description: str,
    prompt: str,
    response: str,
    expected_agent: str | None,
    agent_used: str | None,
    criteria: list[str],
    model: str = DEFAULT_JUDGE_MODEL,
    api_key: str | None = None,
) -> JudgeScore:
    key = api_key or os.environ["OPENROUTER_API_KEY"]
    user_msg = _PROMPT.format(
        description=description,
        prompt=prompt,
        response=response,
        expected_agent=expected_agent or "any",
        agent_used=agent_used or "unknown",
        criteria="\n".join(f"- {c}" for c in criteria),
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
