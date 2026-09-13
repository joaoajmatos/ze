"""Integration test for reprioritize_item's confirmation gate (Phase 127, T033).

Proves — against the *real* `PriorityAgent`/`reprioritize_item` tool and the real
`ze_core` orchestration nodes, not a stand-in — that: (1) capability_check routes
a "priority"/"update" subtask through AWAIT_CONFIRMATION (Mode.CONFIRM, FR-007);
(2) the DRAFT pass never submits a Contribution, because `reprioritize_item` is a
WRITE tool and BaseAgent suppresses WRITE tools while ctx.gate_decision is DRAFT;
(3) only the EXECUTE pass (post await_confirmation resume) actually calls
`submit_reprioritization`'s write path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_agents.registry import register_instance
from ze_agents.types import AgentContext, GateDecision
from ze_core.capability.gate import CapabilityGate
from ze_core.orchestration.nodes.execution import (
    await_confirmation,
    capability_check,
    draft_response,
    execute_tool,
)
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
    subtasks = [
        SubTask(
            agent="priority", intent="update", prompt="deprioritize the berlin move"
        )
    ]
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
        intent="update",
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
    override_store.create.side_effect = lambda o: o
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
async def test_capability_check_routes_priority_update_to_await_confirmation():
    gate = CapabilityGate()
    state = {"envelope": _envelope(), "session_overrides": {}}

    result = await capability_check(state, {"configurable": {"capability_gate": gate}})

    assert result["gate_decision"] == GateDecision.AWAIT_CONFIRMATION


@pytest.mark.asyncio
async def test_draft_pass_never_submits_the_contribution():
    view, override_store = _view_and_store()
    client = _client([(None, _TOOL_CALL), ("I'll deprioritize the Berlin move.", None)])
    _wire_priority_agent(client, view, override_store)

    state = {
        "envelope": _envelope(),
        "agent_context": _ctx(),
        "image_data": None,
    }
    result = await draft_response(state, {"configurable": {}})

    assert result["pending_confirmation"] is True
    assert "Berlin" in result["agent_result"].response
    override_store.create.assert_not_awaited()

    resumed = await await_confirmation(
        {
            "session_id": "s1",
            "envelope": _envelope(),
            "gate_decision": GateDecision.AWAIT_CONFIRMATION,
        },
        {"configurable": {}},
    )
    assert resumed["gate_decision"] == GateDecision.EXECUTE
    override_store.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_pass_submits_the_contribution_only_after_resume():
    view, override_store = _view_and_store()
    client = _client([(None, _TOOL_CALL), ("Done — deprioritized.", None)])
    _wire_priority_agent(client, view, override_store)

    state = {
        "envelope": _envelope(),
        "agent_context": _ctx(),
        "gate_decision": GateDecision.EXECUTE,
        "image_data": None,
    }
    result = await execute_tool(state, {"configurable": {}})

    assert result["agent_result"].response == "Done — deprioritized."
    override_store.create.assert_awaited_once()
