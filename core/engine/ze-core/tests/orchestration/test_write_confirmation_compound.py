"""Compound turns: one pause, no write twice (Phase 181, US3)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langgraph.types import Command

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


def _compound(read_client, write_client):
    h.register_agent("calendar", read_client, ["list_events"])
    h.register_agent("messenger", write_client, ["send_email"])
    return h.compiled_graph(
        [
            SubTask("calendar", "what is on tomorrow"),
            SubTask("messenger", "email Ana the agenda", changes=True),
        ],
        compound=True,
    )


def _reader():
    return h.scripted_client(
        (None, [h.tc("r1", "list_events")]), ("Tomorrow: dentist.", None)
    )


def _sender(*more):
    return h.scripted_client(
        (None, [h.tc("s1", "send_email", to="ana", body="agenda")]), *more
    )


async def _state(graph, cfg):
    return await graph.aget_state(cfg)


async def test_finished_sibling_is_saved_before_the_single_pause() -> None:
    graph = _compound(_reader(), _sender(("Sent.", None)))
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    state = await _state(graph, cfg)
    assert state.next == ("await_write_confirmation",)
    assert [r.agent for r in state.values["subtask_results"]] == ["calendar"]
    assert state.values["completed_subtask_indexes"] == [0]
    assert [c[0] for c in h.calls] == ["list_events"]
    assert [i.tool for i in state.tasks[0].interrupts[0].value.items] == ["send_email"]


async def test_approval_reruns_only_the_parked_subtask() -> None:
    graph = _compound(_reader(), _sender(("Sent.", None)))
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    out = await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    names = [c[0] for c in h.calls]
    assert names.count("list_events") == 1
    assert names.count("send_email") == 1
    assert "calendar: Tomorrow: dentist." in out["final_response"]
    assert "messenger: Sent." in out["final_response"]


async def test_both_subtasks_parking_make_one_confirmation() -> None:
    h.register_agent(
        "calendar",
        h.scripted_client(
            (None, [h.tc("d1", "delete_event", event_id="e1")]), ("Deleted.", None)
        ),
        ["delete_event"],
    )
    h.register_agent("messenger", _sender(("Sent.", None)), ["send_email"])
    graph = h.compiled_graph(
        [SubTask("calendar", "x"), SubTask("messenger", "y")],
        compound=True,
    )
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    state = await _state(graph, cfg)
    confirmation = state.tasks[0].interrupts[0].value
    assert sorted(i.tool for i in confirmation.items) == ["delete_event", "send_email"]
    assert h.calls == []
    await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    assert sorted(c[0] for c in h.calls) == ["delete_event", "send_email"]


async def test_deny_keeps_the_sibling_answer_and_says_nothing_was_sent() -> None:
    graph = _compound(_reader(), _sender(("I did not send it.", None)))
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    out = await graph.ainvoke(Command(resume={"choice": "deny"}), cfg)
    assert [c[0] for c in h.calls] == ["list_events"]
    assert "Tomorrow: dentist." in out["final_response"]
    rows = out["write_outcomes"]
    assert [(r["tool"], r["outcome"]) for r in rows] == [("send_email", "denied")]


async def test_interrupt_is_only_called_from_the_pause_node() -> None:
    sites: list[str] = []
    import langgraph.types as lt

    real = lt.interrupt

    def spy(value):
        import inspect

        sites.append(inspect.stack()[1].function)
        return real(value)

    with patch("ze_core.orchestration.nodes.execution.interrupt", spy):
        graph = _compound(_reader(), _sender(("Sent.", None)))
        cfg = h.thread_config()
        await graph.ainvoke(h.graph_input("go"), cfg)
        await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    assert set(sites) == {"await_write_confirmation"}
