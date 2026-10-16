"""The spend-budget pause is its own confirmation before execution (Phase 181, Q6)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langgraph.types import Command

from ze_agents.registry import clear_registry
from ze_agents.tool import clear_tool_registry
from ze_core.orchestration.nodes.trace import record_trace
from ze_core.routing.types import SubTask

from tests.orchestration import write_confirmation_harness as h


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    h.calls.clear()
    h.register_tools()
    yield
    clear_registry()
    clear_tool_registry()


def _over_budget():
    checker = AsyncMock()
    checker.check = AsyncMock(
        return_value=SimpleNamespace(
            within_budget=False, scope="day", current_spend_usd=4.1, limit_usd=4.0
        )
    )
    return checker


def _graph(client):
    h.register_agent("calendar", client, ["delete_event"])
    return h.compiled_graph(
        [SubTask("calendar", "x")], overrides={"record_trace": record_trace}
    )


async def _pending(graph, cfg):
    state = await graph.aget_state(cfg)
    return state.tasks[0].interrupts[0].value if state.next else None


async def test_over_budget_pauses_before_any_agent_runs() -> None:
    client = h.scripted_client(("done", None))
    graph = _graph(client)
    cfg = h.thread_config(budget_checker=_over_budget())
    await graph.ainvoke(h.graph_input("go"), cfg)
    confirmation = await _pending(graph, cfg)
    assert confirmation.kind == "budget"
    assert confirmation.items[0].tool is None
    assert confirmation.items[0].summary == "$4.10 of $4.00"
    client.complete_with_tools.assert_not_awaited()


async def test_approving_the_budget_runs_the_turn_and_a_write_still_parks() -> None:
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]), ("Deleted.", None)
    )
    graph = _graph(client)
    cfg = h.thread_config(budget_checker=_over_budget())
    await graph.ainvoke(h.graph_input("go"), cfg)
    await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    second = await _pending(graph, cfg)
    assert second.kind == "write" and h.calls == []
    await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    assert h.calls == [("delete_event", {"event_id": "e1"})]


async def test_denying_the_budget_ends_the_turn_with_a_fixed_reply() -> None:
    client = h.scripted_client(("never", None))
    graph = _graph(client)
    cfg = h.thread_config(budget_checker=_over_budget())
    await graph.ainvoke(h.graph_input("go"), cfg)
    out = await graph.ainvoke(Command(resume={"choice": "deny"}), cfg)
    assert "spend limit" in out["final_response"]
    client.complete_with_tools.assert_not_awaited()
    assert out["message_trace"].write_confirmations[0]["outcome"] == "denied"


async def test_retry_mode_skips_the_budget_pause() -> None:
    client = h.scripted_client(("plain reply", None))
    graph = _graph(client)
    cfg = h.thread_config(budget_checker=_over_budget(), retry_mode=True)
    out = await graph.ainvoke(h.graph_input("go"), cfg)
    assert out["agent_result"].response == "plain reply"
