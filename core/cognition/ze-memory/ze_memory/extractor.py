"""LLM-based extraction of user facts and events from a completed conversation turn."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from typing import TYPE_CHECKING

from ze_logging import get_logger
from ze_agents.errors import LLMJsonParseError
from ze_agents.llm_json import parse_llm_json

from ze_memory.defaults import MODEL_SYNTHESIS
from ze_memory.types import Event, Fact, FactAdmission, SpeechAct

if TYPE_CHECKING:
    from ze_memory.types import Entity

log = get_logger(__name__)


class PredicateFamily(StrEnum):
    IDENTITY = "identity"
    PREFERENCE = "preference"
    RELATIONSHIP = "relationship"
    CONSTRAINT = "constraint"
    CONTACT_DETAIL = "contact_detail"


KEEP_FAMILIES: frozenset[str] = frozenset(f.value for f in PredicateFamily)

_TRIVIAL_RE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|yo|sup|good morning|good night)"
    r"[\s!.?]*$",
    re.IGNORECASE,
)

_SYSTEM = """You are the admission gate for durable facts about the USER.

First classify the user speech act. Time-bound reminders, commitments with a
when, lingering concerns, multi-week goals, ingest requests, and filler are
NOT biography facts.

speech_act must be one of:
fact, forget, ingest, clarify, none.

Reminders, lingering concerns, multi-week goals, filler, and cancelling or
abandoning any of them are none, never forget. "Forget the dentist" as
cancelling a ping is none. Biography retract ("forget that I like aisle
seats") is forget. Time-bound reminders still beat biography (time wins).
Do not emit two primary acts for one clause.


Keep facts ONLY when speech_act is fact AND the content is a durable self-fact
in a closed family. Drop greetings, thanks, filler, right-now location, mood,
weather, timed to-dos, and "remember to … on Tuesday".

Closed keep families: identity, preference, relationship, constraint, contact_detail.
If speech_act is not fact, family must be drop and facts must be [].

Respond with JSON only — no markdown:
{"speech_act": "<fact|forget|ingest|clarify|none>",
 "family": "<identity|preference|relationship|constraint|contact_detail|drop>",
 "facts": [{"value": "what was revealed", "confidence": 0.0-1.0}]}
facts must be empty unless speech_act is fact. Predicate of each kept fact is the family name.
"""


_VALUE_SYSTEM = """You phrase one durable fact about the USER.

The user message has already been judged a durable self-fact. Write the fact
itself as a short, third-person-free statement in the user's own language
(for example "prefers aisle seats"). Do not classify. Do not add facts the
user did not state. If there is nothing worth keeping, return an empty list.

Respond with JSON only — no markdown:
{"facts": [{"value": "what was revealed"}]}
"""

_VALUE_CONFIDENCE = 0.8


def fact_extraction_model(settings: Any = None) -> str:
    if settings is None:
        return MODEL_SYNTHESIS
    if isinstance(settings, dict):
        memory = settings.get("memory", {})
        override = (
            memory.get("fact_extraction_model") if isinstance(memory, dict) else None
        )
        if override:
            return override
        return settings.get("models", {}).get("synthesis", MODEL_SYNTHESIS)
    cfg = getattr(settings, "config", None)
    if isinstance(cfg, dict):
        memory = cfg.get("memory", {})
        override = (
            memory.get("fact_extraction_model") if isinstance(memory, dict) else None
        )
        if override:
            return override
        return cfg.get("models", {}).get("synthesis", MODEL_SYNTHESIS)
    return MODEL_SYNTHESIS


def is_trivial_turn(prompt: str) -> bool:
    stripped = prompt.strip()
    if not stripped:
        return True
    return bool(_TRIVIAL_RE.match(stripped))


def admit_speech_act(raw: str | None) -> SpeechAct:
    if not raw:
        return SpeechAct.NONE
    key = raw.strip().lower()
    try:
        return SpeechAct(key)
    except ValueError:
        return SpeechAct.NONE


def admit_family(family: str | None) -> str | None:
    if not family:
        return None
    key = family.strip().lower()
    if key in KEEP_FAMILIES:
        return key
    return None


def parse_fact_response(raw: str) -> list[dict]:
    try:
        parsed = parse_llm_json(raw, expect=(dict, list))
    except LLMJsonParseError:
        return []
    return _admit_parsed(parsed)


def _admit_parsed(parsed: Any) -> list[dict]:
    if isinstance(parsed, dict):
        if "speech_act" not in parsed:
            act = SpeechAct.FACT
        else:
            act = admit_speech_act(parsed.get("speech_act"))
        if act is not SpeechAct.FACT:
            return []
        family = admit_family(parsed.get("family"))
        if family is None:
            return []
        items = parsed.get("facts")
        if not isinstance(items, list):
            return []
        admitted: list[dict] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("value"):
                continue
            admitted.append(
                {
                    "predicate": family,
                    "value": str(item["value"]),
                    "confidence": float(item.get("confidence", 0.8)),
                }
            )
        return admitted
    if isinstance(parsed, list):
        admitted = []
        for item in parsed:
            if not isinstance(item, dict) or not item.get("value"):
                continue
            family = admit_family(
                item.get("family") or item.get("predicate") or item.get("key")
            )
            if family is None:
                continue
            admitted.append(
                {
                    "predicate": family,
                    "value": str(item["value"]),
                    "confidence": float(item.get("confidence", 0.8)),
                }
            )
        return admitted
    return []


def raw_to_facts(raw: list[dict]) -> list[Fact]:
    return [
        Fact(
            id=None,
            subject_id=None,
            predicate=f["predicate"],
            object_text=None,
            object_id=None,
            value=f["value"],
            confidence=float(f.get("confidence", 0.8)),
        )
        for f in raw
        if isinstance(f, dict) and f.get("predicate") and f.get("value")
    ]


async def extract_facts(
    client: Any,
    *,
    prompt: str,
    response: str,
    model: str,
) -> list[Fact]:
    if response.startswith("[ERROR]"):
        return []
    if is_trivial_turn(prompt):
        return []
    try:
        raw = await client.complete(
            messages=[
                {
                    "role": "user",
                    "content": f"User said: {prompt}\n\nAssistant replied: {response[:1000]}",
                }
            ],
            model=model,
            system=_SYSTEM,
            max_tokens=300,
        )
        return raw_to_facts(parse_fact_response(raw))
    except Exception as exc:
        log.warning("memory_fact_extraction_failed", error=str(exc))
        return []


async def write_fact_values(
    client: Any,
    *,
    prompt: str,
    response: str,
    family: str,
    model: str,
) -> list[Fact]:
    """Narrowed value writer: phrases fact text only; the family is already decided."""
    try:
        raw = await client.complete(
            messages=[
                {
                    "role": "user",
                    "content": f"User said: {prompt}\n\nAssistant replied: {response[:1000]}",
                }
            ],
            model=model,
            system=_VALUE_SYSTEM,
            max_tokens=200,
        )
        parsed = parse_llm_json(raw, expect=dict)
    except Exception as exc:
        log.warning("memory_fact_value_writer_failed", error=str(exc))
        return []
    items = parsed.get("facts") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return []
    return raw_to_facts(
        [
            {
                "predicate": family,
                "value": str(item["value"]),
                "confidence": _VALUE_CONFIDENCE,
            }
            for item in items
            if isinstance(item, dict) and item.get("value")
        ]
    )


def parse_event_response(raw: str) -> list[dict]:
    try:
        parsed = parse_llm_json(raw, expect=list)
    except LLMJsonParseError:
        return []
    return [
        e
        for e in parsed
        if isinstance(e, dict) and e.get("title") and e.get("event_type")
    ]


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def raw_to_events(raw: list[dict]) -> list[Event]:
    return [
        Event(
            id=None,
            event_type=e.get("event_type", "other"),
            title=e["title"],
            start_at=_parse_dt(e.get("start_at")),
            end_at=_parse_dt(e.get("end_at")),
            participant_names=[str(p) for p in e.get("participants", []) if p],
            outcome=e.get("outcome") or None,
        )
        for e in raw
        if isinstance(e, dict) and e.get("title") and e.get("event_type")
    ]


def raw_to_entities(raw: list[dict]) -> list["Entity"]:
    from ze_memory.types import Entity

    return [
        Entity(
            id=None,
            entity_type=e.get("entity_type", "concept"),
            canonical_name=str(e["name"]),
            aliases=[str(a) for a in e.get("aliases", []) if a],
            attrs={},
        )
        for e in raw
        if isinstance(e, dict) and e.get("name") and e.get("entity_type")
    ]


_TURN_GRAPH_SYSTEM = (
    "You extract events and named entities from AI assistant conversations. "
    "An event is anything that happened (or will happen) at a point in time that is worth remembering: "
    "meetings, calls, trips, appointments, meals, decisions made, accomplishments achieved, "
    "milestones reached, experiences had, or any other significant occurrence. "
    "Only extract events the user explicitly mentioned — do not infer. "
    "An entity is a proper noun explicitly mentioned: a person, organisation, place, product, project, or concept. "
    "Do not extract generic terms, pronouns, or inferred entities. "
    "Return one JSON object — no markdown, just the object — with two arrays. "
    'Each event: {"event_type": "meeting|call|trip|appointment|meal|decision|accomplishment|experience|milestone|other", '
    '"title": "concise description", '
    '"start_at": "ISO8601 datetime or null", "end_at": "ISO8601 datetime or null", '
    '"participants": ["name1", "name2"], '
    '"outcome": "result/outcome if already past, or null"}. '
    'Each entity: {"name": "canonical name", '
    '"entity_type": "person|organisation|place|product|project|concept", '
    '"aliases": ["alt name 1"]}. '
    'Shape: {"events": [...], "entities": [...]}. Use [] for an array with nothing to extract.'
)


@dataclass
class TurnProposals:
    events: list[Event] = field(default_factory=list)
    entities: list["Entity"] = field(default_factory=list)


async def extract_turn_graph(
    client: Any,
    *,
    prompt: str,
    response: str,
    model: str,
) -> TurnProposals:
    """One request for the turn's events and entities (they used to be two)."""
    if response.startswith("[ERROR]"):
        return TurnProposals()
    try:
        raw = await client.complete(
            messages=[
                {
                    "role": "user",
                    "content": f"User said: {prompt}\n\nAssistant replied: {response[:1000]}",
                }
            ],
            model=model,
            system=_TURN_GRAPH_SYSTEM,
            max_tokens=700,
        )
        parsed = parse_llm_json(raw, expect=dict)
    except LLMJsonParseError:
        return TurnProposals()
    except Exception as exc:
        log.warning("memory_turn_extraction_failed", error=str(exc))
        return TurnProposals()

    events = parsed.get("events")
    entities = parsed.get("entities")
    return TurnProposals(
        events=raw_to_events(events) if isinstance(events, list) else [],
        entities=raw_to_entities(
            [
                e
                for e in entities
                if isinstance(e, dict) and e.get("name") and e.get("entity_type")
            ]
            if isinstance(entities, list)
            else []
        ),
    )


async def gather_turn_proposals(
    configurable: dict,
    *,
    prompt: str,
    response: str,
) -> TurnProposals:
    """Events and entities of a conversation turn; a trivial turn makes no request."""
    client = configurable.get("openrouter_client")
    if client is None or is_trivial_turn(prompt):
        return TurnProposals()

    settings = configurable.get("settings")
    settings_dict = (
        settings.config
        if settings is not None and hasattr(settings, "config")
        else settings
    )
    model = fact_extraction_model(settings_dict)
    return await extract_turn_graph(
        client, prompt=prompt, response=response, model=model
    )


async def gather_fact_proposals(
    configurable: dict,
    *,
    agent: str,
    prompt: str,
    response: str,
) -> FactAdmission:
    """Admit durable facts from the turn. Explicit remember writes are tools."""
    client = configurable.get("openrouter_client")
    if client is None or is_trivial_turn(prompt) or response.startswith("[ERROR]"):
        return FactAdmission(path="none")

    settings = configurable.get("settings")
    settings_dict = (
        settings.config
        if settings is not None and hasattr(settings, "config")
        else settings
    )
    model = fact_extraction_model(settings_dict)

    extracted = await extract_facts(
        client,
        prompt=prompt,
        response=response,
        model=model,
    )
    for fact in extracted:
        fact.agent = agent
    return FactAdmission(facts=extracted, path="haiku")
