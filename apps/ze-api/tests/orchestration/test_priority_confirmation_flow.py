"""reprioritize_item runs without a confirmation (Phase 127 / 181 audit).

Against the *real* `PriorityAgent`/`reprioritize_item` tool and the real
`execute_tool` node: the tool opts out of asking first (a decaying override the
user can reorder again), so the override is submitted in the same turn.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_agents.registry import register_instance
from ze_agents.types import AgentContext
from ze_core.orchestration.nodes.execution import execute_tool
from ze_core.routing.types import RoutingEnvelope, SubTask
from ze_memory.types import MemoryContext

import ze_priority.agent  # noqa: F401 — fires @agent registration for "priority"
import ze_priority.tools  # noqa: F401 — registers reprioritize_item
from ze_priority.types import PriorityItem, PriorityRanking

UTC = timezone.utc


def _item(title: str, rank: int) -> PriorityItem:
    return PriorityItem(
        source_kind="loop",
        claim_kind=ClaimKind.PRIORITY,
        source_id=uuid4(),
        title=title,
        signal=None,
        priority=Confidence(
            value=1.0 - rank * 0.1, decay_profile=DecayProfile.TIME_LINEAR
        ),
        rank=rank,
        activity_at=datetime.now(UTC),
    )


class _FakeEmbedder:
    """Matches "berlin" strongly to the item titled "the berlin move" only."""

    def encode(self, text: str) -> np.ndarray:
        lowered = text.lower()
        return np.array([1.0 if "berlin" in lowered else 0.0, 1.0])


def _client(responses: list) -> MagicMock:
    client = MagicMock()
    client.complete_with_tools = AsyncMock(side_effect=responses)
    client.complete = AsyncMock(return_value="fallback text")
    return client


def _wire_priority_agent(client, view, override_store) -> None:
    instance = ze_priority.agent.PriorityAgent(
        openrouter_client=client,
        priority_view=view,
        override_store=override_store,
        collision_store=AsyncMock(),
        nli_client=AsyncMock(),
        embedder=_FakeEmbedder(),
    )
    register_instance("priority", instance)


def _envelope() -> RoutingEnvelope:
    subtasks = [SubTask(agent="priority", prompt="deprioritize the berlin move")]
    return RoutingEnvelope(
        primary_agent="priority",
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=False,
        subtasks=subtasks,
        requires_synthesis=False,
        is_sequential=False,
    )


def _ctx() -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt="deprioritize the berlin move",
        memory=MemoryContext(),
        messages=[{"role": "user", "content": "deprioritize the berlin move"}],
    )


def _view_and_store():
    berlin, other = _item("the berlin move", 1), _item("quarterly report", 2)
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=[berlin, other],
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )
    override_store = AsyncMock()
    override_store.create.side_effect = lambda o: (o, None)
    return view, override_store


_TOOL_CALL = [
    {
        "id": "c1",
        "name": "reprioritize_item",
        "arguments": {
            "item_description": "the berlin move",
            "requested_relation": "less_urgent",
            "pin": False,
        },
    }
]


@pytest.mark.asyncio
async def test_the_override_is_submitted_without_a_confirmation():
    view, override_store = _view_and_store()
    client = _client([(None, _TOOL_CALL), ("Done — deprioritized.", None)])
    _wire_priority_agent(client, view, override_store)

    state = {
        "envelope": _envelope(),
        "agent_context": _ctx(),
        "image_data": None,
    }
    result = await execute_tool(state, {"configurable": {}})

    assert result["agent_result"].response == "Done — deprioritized."
    override_store.create.assert_awaited_once()
    [call] = result["agent_result"].tool_calls
    assert call.success is True
    assert call.undo is not None
    assert call.undo["prior_override_id"] is None
