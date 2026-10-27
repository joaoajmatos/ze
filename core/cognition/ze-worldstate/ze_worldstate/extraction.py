from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from ze_agents.client import LLMClient
from ze_logging import get_logger

from ze_worldstate.decision import CommitDecision
from ze_worldstate.types import TitleWriterResult

log = get_logger(__name__)

DEFAULT_EXTRACTION_MODEL = "anthropic/claude-haiku-4-5"

_SYSTEM_PROMPT = """You are the relevance gate for Ze's open-loop substrate. Given a
short piece of text, decide whether it implies a genuine unfinished commitment,
task, or concern the user (or someone in their life) still needs to act on —
an "open loop" (e.g. "I need to renew my passport", "I told Maria I'd send the
contract") — OR whether it reports that a previously-open commitment is now done
(e.g. "I followed up with the accountant, it's done").

Be conservative: ordinary conversational content ("what's the weather",
"thanks!", small talk, questions) is neither.

Also decide whether the user is *explicitly declaring* the commitment themselves
("remind me I need to...", "I need to...", "I have to...") as opposed to it being
merely implied/inferred from context.

Also decide, only when `is_loop` is true, whether the text implies a specific
timeframe by which the commitment should be resolved (e.g. "by Friday", "next
week") — if so, express it as a whole number of days from now; otherwise omit it.

Respond with a JSON object only:
{
  "is_loop": true|false,
  "title": "short human-readable title, or empty string",
  "explicit_declaration": true|false,
  "resolves_existing": true|false,
  "implied_window_days": <integer, optional>
}
`resolves_existing` is true only when the text reports an existing commitment as
done/finished — in that case `is_loop` should be false and `title` is the short
description of the commitment that was resolved.
"""


class _ExtractionGateResult:
    __slots__ = (
        "is_loop",
        "title",
        "explicit_declaration",
        "resolves_existing",
        "implied_window_days",
    )

    def __init__(
        self,
        is_loop: bool,
        title: str,
        explicit_declaration: bool,
        resolves_existing: bool,
        implied_window_days: int | None = None,
    ) -> None:
        self.is_loop = is_loop
        self.title = title
        self.explicit_declaration = explicit_declaration
        self.resolves_existing = resolves_existing
        self.implied_window_days = implied_window_days


async def _run_extraction_gate(
    text: str, llm_client: LLMClient, model: str
) -> _ExtractionGateResult | None:
    try:
        raw = await llm_client.complete(
            [{"role": "user", "content": text}],
            model=model,
            system=_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        parsed = _loads_json(raw)
    except Exception as exc:
        log.warning("loop_extraction_gate_failed", error=str(exc))
        return None

    raw_window = parsed.get("implied_window_days")
    implied_window_days = (
        int(raw_window) if isinstance(raw_window, (int, float)) else None
    )

    return _ExtractionGateResult(
        is_loop=bool(parsed.get("is_loop")),
        title=str(parsed.get("title") or "").strip(),
        explicit_declaration=bool(parsed.get("explicit_declaration")),
        resolves_existing=bool(parsed.get("resolves_existing")),
        implied_window_days=implied_window_days,
    )


_WRITER_PROMPT = """You write the short title of one open loop for Ze. The text has already
been judged: it {what}. Reply with a JSON object only:
{{"title": "short human-readable title"{window_field}}}
The title names the commitment itself, in the language of the text, in under ten words.{window_rule}
"""

_WRITER_CREATE = ("implies an unfinished commitment the user still has to act on", True)
_WRITER_RESOLVE = ("reports that a commitment the user had is now done", False)


def _loads_json(raw: str) -> Any:
    """Haiku wraps JSON replies in a ```json fence even with response_format set."""
    text = raw.strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in reply")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def _whole_days(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, float) and raw.is_integer() and raw > 0:
        return int(raw)
    return None


async def write_loop_title(
    text: str, kind: str, llm_client: LLMClient, model: str
) -> TitleWriterResult | None:
    """Haiku writes the title (and, for creates, an implied window). It never decides existence."""
    what, with_window = _WRITER_CREATE if kind == "create" else _WRITER_RESOLVE
    system = _WRITER_PROMPT.format(
        what=what,
        window_field=', "implied_window_days": <integer, optional>'
        if with_window
        else "",
        window_rule=(
            " Include `implied_window_days` only if the text names a timeframe, as a whole"
            " number of days from now; otherwise omit it."
            if with_window
            else ""
        ),
    )
    try:
        raw = await llm_client.complete(
            [{"role": "user", "content": text}],
            model=model,
            system=system,
            temperature=0.0,
            max_tokens=120,
            response_format={"type": "json_object"},
        )
        parsed = _loads_json(raw)
        title = str(parsed.get("title") or "").strip()
    except Exception as exc:
        log.warning("loop_title_writer_failed", error=str(exc))
        return None
    if not title:
        log.warning("loop_title_writer_empty")
        return None
    window = _whole_days(parsed.get("implied_window_days")) if with_window else None
    return TitleWriterResult(title=title, implied_window_days=window)


async def resolve_entities(entity_resolver: Any, text: str) -> list[UUID]:
    if entity_resolver is None:
        return []
    try:
        return list(await entity_resolver(text))
    except Exception as exc:
        log.warning("loop_entity_resolution_failed", error=str(exc))
        return []


async def decide_with_109_gate(
    text: str, llm_client: LLMClient, model: str
) -> CommitDecision:
    """The Haiku relevance gate as a `CommitDecision`; a failed gate holds."""
    gate = await _run_extraction_gate(text, llm_client, model)
    if gate is None:
        return CommitDecision("hold", "gate_failed")
    if gate.resolves_existing and gate.title:
        return CommitDecision("resolve", "gate_resolves", title=gate.title)
    if not gate.is_loop or not gate.title:
        return CommitDecision("hold", "gate_not_loop")
    kind = "create_declared" if gate.explicit_declaration else "create_suspected"
    return CommitDecision(
        kind,
        "gate_explicit" if gate.explicit_declaration else "gate_implied",
        title=gate.title,
        window_days=gate.implied_window_days,
    )
