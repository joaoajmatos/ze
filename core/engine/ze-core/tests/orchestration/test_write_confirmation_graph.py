"""Single-path write confirmation through the real graph nodes (Phase 181, D3)."""

from __future__ import annotations

import pytest
from langgraph.types import Command

from ze_agents.park import WriteConfirmation
from ze_agents.registry import clear_registry
from ze_agents.tool import clear_tool_registry
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


def _single(client, tools=("list_events", "delete_event", "send_email")):
    h.register_agent("calendar", client, list(tools))
    return h.compiled_graph([SubTask(agent="calendar", prompt="delete my 3pm")])


async def _open_confirmation(graph, cfg) -> WriteConfirmation:
    state = await graph.aget_state(cfg)
    assert state.next == ("await_write_confirmation",)
    payload = state.tasks[0].interrupts[0].value
    assert isinstance(payload, WriteConfirmation)
    return payload


async def test_park_pauses_once_and_approval_runs_the_call_once() -> None:
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]),
        ("Deleted your 3pm.", None),
    )
    graph = _single(client)
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("delete my 3pm"), cfg)

    confirmation = await _open_confirmation(graph, cfg)
    assert h.calls == []
    assert (confirmation.kind, confirmation.round, confirmation.status) == (
        "write",
        1,
        "open",
    )
    assert len(confirmation.items) == 1
    item = confirmation.items[0]
    assert (item.tool, item.agent, item.effect_phrase) == (
        "delete_event",
        "calendar",
        "delete a calendar event",
    )

    out = await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    assert h.calls == [("delete_event", {"event_id": "e1"})]
    assert out["agent_result"].response == "Deleted your 3pm."
    state = await graph.aget_state(cfg)
    assert state.next == ()


async def test_disabled_agent_ends_blocked() -> None:
    h.register_agent("calendar", h.scripted_client(), ["list_events"], enabled=False)
    graph = h.compiled_graph([SubTask(agent="calendar", prompt="hi")])
    cfg = h.thread_config()
    out = await graph.ainvoke(h.graph_input("hi"), cfg)
    assert out.get("agent_result") is None
    assert (await graph.aget_state(cfg)).next == ()
    assert h.calls == []
