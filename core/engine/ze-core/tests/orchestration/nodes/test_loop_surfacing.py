from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from ze_core.orchestration.nodes.loop_surfacing import surface_loops
from ze_memory.types import Entity, MemoryContext
from ze_core.routing.types import RoutingEnvelope, SubTask


@dataclass
class _Mention:
    source_id: UUID = field(default_factory=uuid4)
    source_kind: str = "loop"
    title: str = "Send Maria the contract"
    mention_text: str = (
        'It looks like "Send Maria the contract" may still be open — no update since.'
    )


def _envelope(is_compound: bool = False) -> RoutingEnvelope:
    st = SubTask(agent="research", intent="read", prompt="hi Maria")
    return RoutingEnvelope(
        primary_agent="research",
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=is_compound,
        subtasks=[st],
        requires_synthesis=False,
    )


def _memory_ctx(entity_ids: list[UUID] | None = None) -> MemoryContext:
    ids = entity_ids or [uuid4()]
    entities = [
        Entity(id=eid, entity_type="person", canonical_name=f"Entity-{i}")
        for i, eid in enumerate(ids)
    ]
    return MemoryContext(entities=entities)


def _surfacer(mentions: list | None = None, *, global_query: bool = False) -> Any:
    s = AsyncMock()
    s.inline_mentions = AsyncMock(
        return_value=[_Mention()] if mentions is None else mentions
    )
    s.is_global_open_query = lambda _prompt: global_query
    return s


def _config(surfacer: Any = None) -> dict:
    return {"configurable": {"turn_surfacer": surfacer}}


def _state(
    memory_ctx: MemoryContext | None = None,
    components: list | None = None,
    subtask_results: list | None = None,
    agent_result: Any = None,
    is_compound: bool = False,
    prompt: str = "hi Maria",
) -> dict:
    from ze_agents.types import AgentResult

    return {
        "prompt": prompt,
        "envelope": _envelope(is_compound),
        "memory_context": memory_ctx or _memory_ctx(),
        "components": components or [],
        "subtask_results": subtask_results or [],
        "agent_result": agent_result
        or AgentResult(agent="research", response="Main answer."),
    }


async def test_surfaces_mention_when_surfacer_present():
    surfacer = _surfacer()
    result = await surface_loops(_state(), _config(surfacer=surfacer))

    assert result["open_item_mentions"]
    assert len(result["components"]) == 1
    assert result["components"][0]["type"] == "open_items"
    surfacer.inline_mentions.assert_awaited_once()


async def test_no_surfacer_configured_returns_empty():
    result = await surface_loops(_state(), _config(surfacer=None))
    assert result == {}


async def test_no_entities_skips_surfacing():
    surfacer = _surfacer()
    ctx = MemoryContext(entities=[])
    result = await surface_loops(_state(memory_ctx=ctx), _config(surfacer=surfacer))
    assert result == {}
    surfacer.inline_mentions.assert_not_awaited()


async def test_no_mentions_yields_no_update():
    surfacer = _surfacer(mentions=[])
    result = await surface_loops(_state(), _config(surfacer=surfacer))
    assert result == {}


async def test_surfacer_exception_drops_section_silently():
    surfacer = AsyncMock()
    surfacer.is_global_open_query = lambda _p: False
    surfacer.inline_mentions = AsyncMock(side_effect=RuntimeError("boom"))
    result = await surface_loops(_state(), _config(surfacer=surfacer))
    assert result == {}


async def test_single_turn_sets_final_response_with_mention_text():
    surfacer = _surfacer()
    result = await surface_loops(_state(), _config(surfacer=surfacer))
    assert "final_response" in result
    assert "It looks like" in result["final_response"]
    assert "Main answer." in result["final_response"]


async def test_compound_turn_does_not_set_final_response():
    from ze_agents.types import AgentResult

    surfacer = _surfacer()
    subtask_results = [AgentResult(agent="research", response="data")]
    result = await surface_loops(
        _state(is_compound=True, subtask_results=subtask_results, agent_result=None),
        _config(surfacer=surfacer),
    )
    assert "final_response" not in result
    assert result["open_item_mentions"]


async def test_existing_components_are_preserved():
    surfacer = _surfacer()
    existing = [{"type": "card", "body": "existing"}]
    result = await surface_loops(_state(components=existing), _config(surfacer=surfacer))
    assert result["components"][0]["type"] == "card"
    assert result["components"][1]["type"] == "open_items"


async def test_global_open_query_skips_unsolicited_append():
    surfacer = _surfacer(global_query=True)
    result = await surface_loops(
        _state(prompt="what's open right now"), _config(surfacer=surfacer)
    )
    assert result == {}
    surfacer.inline_mentions.assert_not_awaited()
