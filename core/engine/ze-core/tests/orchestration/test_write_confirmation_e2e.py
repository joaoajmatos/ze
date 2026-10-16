"""End-to-end write confirmation through the real graph nodes (Phase 181, US1/US2)."""

from __future__ import annotations

import pytest
from langgraph.types import Command

from ze_agents.delegate import DELEGATE_TOOL_NAME
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


async def _pending(graph, cfg) -> WriteConfirmation | None:
    state = await graph.aget_state(cfg)
    if not state.next:
        return None
    return state.tasks[0].interrupts[0].value


def _graph(client, tools):
    h.register_agent("calendar", client, tools)
    return h.compiled_graph([SubTask("calendar", "do it")])


async def test_opt_out_write_runs_without_a_confirmation() -> None:
    graph = _graph(
        h.scripted_client(
            (None, [h.tc("c1", "ingest_text", text="article")]), ("Saved it.", None)
        ),
        ["ingest_text"],
    )
    cfg = h.thread_config()
    out = await graph.ainvoke(h.graph_input("save this"), cfg)
    assert await _pending(graph, cfg) is None
    assert h.calls == [("ingest_text", {"text": "article"})]
    assert out["agent_result"].response == "Saved it."


async def test_reversible_write_runs_without_a_confirmation() -> None:
    graph = _graph(
        h.scripted_client(
            (None, [h.tc("c1", "archive_note", note_id="n1")]), ("Archived.", None)
        ),
        ["archive_note"],
    )
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("archive it"), cfg)
    assert await _pending(graph, cfg) is None
    assert h.calls == [("archive_note", {"note_id": "n1"})]


async def test_read_then_write_in_one_response_asks_once_and_reads_once() -> None:
    graph = _graph(
        h.scripted_client(
            (
                None,
                [h.tc("c1", "list_events"), h.tc("c2", "delete_event", event_id="e1")],
            ),
            ("Deleted.", None),
        ),
        ["list_events", "delete_event"],
    )
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("delete my 3pm"), cfg)
    assert h.calls == [("list_events", {})]
    assert len((await _pending(graph, cfg)).items) == 1

    await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)
    assert h.calls == [
        ("list_events", {}),
        ("delete_event", {"event_id": "e1"}),
    ]


async def test_conductor_delegation_shows_one_item_and_resumes_the_conductor() -> None:
    h.register_agent(
        "messenger",
        h.scripted_client((None, [h.tc("k1", "send_email", to="ana", body="hi")])),
        ["send_email"],
    )
    companion_client = h.scripted_client(
        (
            None,
            [
                h.tc(
                    "d1",
                    DELEGATE_TOOL_NAME,
                    agent_name="messenger",
                    objective="email Ana",
                )
            ],
        ),
        ("I emailed Ana.", None),
    )
    h.register_agent("companion", companion_client, [DELEGATE_TOOL_NAME])
    graph = h.compiled_graph([SubTask("companion", "email Ana")])
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("email Ana"), cfg)

    confirmation = await _pending(graph, cfg)
    assert [(i.agent, i.tool) for i in confirmation.items] == [
        ("messenger", "send_email")
    ]
    assert h.calls == []

    out = await graph.ainvoke(
        Command(
            resume={
                "choice": "approve",
                "edits": {confirmation.items[0].item_id: "edited hi"},
            }
        ),
        cfg,
    )
    assert h.calls == [("send_email", {"to": "ana", "body": "edited hi"})]
    assert out["agent_result"].response == "I emailed Ana."
