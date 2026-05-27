"""LLM-based extraction of user facts from a completed conversation turn."""

from __future__ import annotations

import json
from typing import Any

from ze_core.defaults import MODEL_SYNTHESIS
from ze_core.logging import get_logger
from ze_core.memory.types import UserFact

log = get_logger(__name__)

_SYSTEM = (
    "You extract facts about the user from AI assistant conversations. "
    "Only extract facts the user explicitly revealed about themselves "
    "(name, preferences, job, location, habits, goals, etc.). "
    "Return a JSON array — no markdown, no explanation, just the array. "
    'Each item: {"key": "snake_case_label", "value": "what was revealed", "confidence": 0.0-1.0}. '
    "If no user facts are present, return []."
)


def fact_extraction_model(settings: Any = None) -> str:
    """Model used for post-turn fact extraction (defaults to synthesis / Haiku)."""
    if settings is None:
        return MODEL_SYNTHESIS
    if isinstance(settings, dict):
        memory = settings.get("memory", {})
        override = memory.get("fact_extraction_model") if isinstance(memory, dict) else None
        if override:
            return override
        return settings.get("models", {}).get("synthesis", MODEL_SYNTHESIS)
    cfg = getattr(settings, "config", None)
    if isinstance(cfg, dict):
        memory = cfg.get("memory", {})
        override = memory.get("fact_extraction_model") if isinstance(memory, dict) else None
        if override:
            return override
        return cfg.get("models", {}).get("synthesis", MODEL_SYNTHESIS)
    return MODEL_SYNTHESIS


def parse_fact_response(raw: str) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            return []
        return [
            {
                "key": str(f["key"]),
                "value": str(f["value"]),
                "confidence": float(f.get("confidence", 0.8)),
            }
            for f in parsed
            if isinstance(f, dict) and "key" in f and "value" in f
        ]
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


def raw_to_user_facts(raw: list[dict], *, agent: str = "global") -> list[UserFact]:
    return [
        UserFact(
            key=f["key"],
            value=f["value"],
            agent=agent,
            confidence=float(f.get("confidence", 0.8)),
        )
        for f in raw
        if isinstance(f, dict) and f.get("key") and f.get("value")
    ]


def merge_fact_proposals(explicit: list[UserFact], extracted: list[UserFact]) -> list[UserFact]:
    """Agent-supplied proposals override extracted facts with the same key."""
    by_key = {f.key: f for f in extracted}
    for fact in explicit:
        by_key[fact.key] = fact
    return list(by_key.values())


async def extract_user_facts(
    client: Any,
    *,
    prompt: str,
    response: str,
    model: str,
    agent: str = "global",
) -> list[UserFact]:
    if response.startswith("[ERROR]"):
        return []
    try:
        raw = await client.complete(
            messages=[{
                "role": "user",
                "content": f"User said: {prompt}\n\nAssistant replied: {response[:1000]}",
            }],
            model=model,
            system=_SYSTEM,
            max_tokens=300,
        )
        return raw_to_user_facts(parse_fact_response(raw), agent=agent)
    except Exception as exc:
        log.warning("memory_fact_extraction_failed", error=str(exc))
        return []


async def gather_fact_proposals(
    configurable: dict,
    *,
    agent: str,
    prompt: str,
    response: str,
    explicit: list,
) -> list[UserFact]:
    """Merge agent-supplied proposals with LLM-extracted facts from the turn."""
    explicit_facts = [_coerce_user_fact(f, agent) for f in explicit]
    explicit_facts = [f for f in explicit_facts if f is not None]

    client = configurable.get("openrouter_client")
    if client is None:
        return explicit_facts

    settings = configurable.get("settings")
    settings_dict = settings.config if settings is not None and hasattr(settings, "config") else settings
    model = fact_extraction_model(settings_dict)
    extracted = await extract_user_facts(
        client,
        prompt=prompt,
        response=response,
        model=model,
        agent=agent,
    )
    return merge_fact_proposals(explicit_facts, extracted)


def _coerce_user_fact(item: Any, agent: str) -> UserFact | None:
    if isinstance(item, UserFact):
        return item
    if isinstance(item, dict) and item.get("key") and item.get("value"):
        return UserFact(
            key=str(item["key"]),
            value=str(item["value"]),
            agent=item.get("agent", agent),
            confidence=float(item.get("confidence", 0.8)),
        )
    return None
