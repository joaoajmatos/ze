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


async def test_resumed_reply_uses_the_real_tool_result() -> None:
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]),
        ("Deleted e1.", None),
    )
    graph = _single(client)
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("delete my 3pm"), cfg)
    await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    sent = client.complete_with_tools.call_args.kwargs["messages"]
    assert sent[-1]["content"] == "deleted e1"


async def test_a_resumed_loop_that_parks_again_opens_round_two() -> None:
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]),
        (None, [h.tc("c2", "send_email", to="ana", body="hi")]),
        ("All done.", None),
    )
    graph = _single(client)
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    first = await _open_confirmation(graph, cfg)
    await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    second = await _open_confirmation(graph, cfg)
    assert second.round == 2
    assert second.request_id != first.request_id
    assert [i.tool for i in second.items] == ["send_email"]


async def test_the_fourth_round_is_refused_not_run() -> None:
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]),
        (None, [h.tc("c2", "delete_event", event_id="e2")]),
        (None, [h.tc("c3", "delete_event", event_id="e3")]),
        (None, [h.tc("c4", "delete_event", event_id="e4")]),
        ("I could not do the last one.", None),
    )
    graph = _single(client)
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    for round_ in (1, 2, 3):
        assert (await _open_confirmation(graph, cfg)).round == round_
        await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    assert (await graph.aget_state(cfg)).next == ()
    assert [c[1]["event_id"] for c in h.calls] == ["e1", "e2", "e3"]
    sent = client.complete_with_tools.call_args.kwargs["messages"]
    assert "ask them in your reply" in sent[-1]["content"]


async def test_restart_resumes_from_the_checkpoint() -> None:
    from langgraph.checkpoint.memory import InMemorySaver

    from ze_core.checkpoint_serde import build_checkpoint_serde

    saver = InMemorySaver(serde=build_checkpoint_serde())
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]),
    )
    h.register_agent("calendar", client, ["delete_event"])
    sub = [SubTask(agent="calendar", prompt="x")]
    cfg = h.thread_config()
    await h.compiled_graph(sub, saver=saver).ainvoke(h.graph_input("go"), cfg)
    assert h.calls == []

    clear_registry()
    client2 = h.scripted_client(("Deleted.", None))
    h.register_agent("calendar", client2, ["delete_event"])
    fresh = h.compiled_graph(sub, saver=saver)
    out = await fresh.ainvoke(Command(resume={"choice": "approve"}), cfg)
    assert h.calls == [("delete_event", {"event_id": "e1"})]
    assert out["agent_result"].response == "Deleted."


async def test_write_outcomes_hold_one_row_per_item_per_round() -> None:
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]),
        (None, [h.tc("c2", "send_email", to="ana", body="hi")]),
        ("ok", None),
    )
    graph = _single(client)
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    out = await graph.ainvoke(Command(resume={"choice": "deny"}), cfg)
    rows = out["write_outcomes"]
    assert [(r["round"], r["tool"], r["outcome"]) for r in rows] == [
        (1, "delete_event", "approved"),
        (2, "send_email", "denied"),
    ]


def _graph_with_real_trace(client):
    from ze_core.orchestration.nodes.trace import record_trace

    h.register_agent("calendar", client, ["delete_event"])
    return h.compiled_graph(
        [SubTask(agent="calendar", prompt="x")],
        overrides={"record_trace": record_trace},
    )


async def test_deny_runs_nothing_and_adds_the_didnt_line() -> None:
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]),
        ("Anything else?", None),
    )
    graph = _graph_with_real_trace(client)
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("delete"), cfg)
    out = await graph.ainvoke(Command(resume={"choice": "deny"}), cfg)
    assert h.calls == []
    assert out["final_response"].count("Okay, I didn't delete a calendar event.") == 1
    assert out["agent_result"].response == out["final_response"]
    assert out["message_trace"].write_confirmations[0]["outcome"] == "denied"


async def test_timeout_is_a_denial_with_its_own_outcome() -> None:
    client = h.scripted_client(
        (None, [h.tc("c1", "delete_event", event_id="e1")]),
        ("Okay, I didn't delete a calendar event.", None),
    )
    graph = _graph_with_real_trace(client)
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("delete"), cfg)
    out = await graph.ainvoke(Command(resume={"choice": "timeout"}), cfg)
    assert h.calls == []
    assert out["agent_result"].response.count("Okay, I didn't") == 1
    assert out["message_trace"].write_confirmations[0]["outcome"] == "timed_out"
