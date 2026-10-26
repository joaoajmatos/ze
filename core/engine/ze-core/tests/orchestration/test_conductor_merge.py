"""Conductor state comes back from every child run in one value (phase 200, US2).

`AgentState` is the only copy between graph steps: one tally per execution pass, one
ledger slot per subtask, caps per turn across subtasks, and the same totals across a pause.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.types import Command

from ze_agents.base_agent import BaseAgent
from ze_agents.delegate import DELEGATE_TURN_CAP
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.tool import clear_tool_registry
from ze_agents.types import AgentContext, AgentResult
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


def keyed_client(script: dict[str, list]):
    """Answers by the first message's text, so concurrent subtasks never share a queue."""
    client = MagicMock()

    async def _complete(**kw):
        return script[kw["messages"][0]["content"]].pop(0)

    client.complete_with_tools = AsyncMock(side_effect=_complete)
    client.complete = AsyncMock(return_value="fallback")
    return client


def register(name: str, client, tools: list[str]) -> None:
    async def _run(self, ctx: AgentContext) -> AgentResult:
        text, tcs = await self.agentic_loop(
            ctx,
            client,
            [{"role": "user", "content": ctx.prompt}],
            system="s",
            tool_names=list(tools),
        )
        return AgentResult(agent=self.name, response=text, tool_calls=tcs)

    cls = type(
        f"_Agent_{name}",
        (BaseAgent,),
        {
            "name": name,
            "description": name,
            "tools": list(tools),
            "run": _run,
            "enabled": True,
        },
    )
    agent(cls)
    register_instance(name, cls())


def delegate(call_id: str, to: str, objective: str):
    return h.tc(call_id, "delegate_to_agent", agent_name=to, objective=objective)


def brief(objective: str) -> str:
    return f"Objective: {objective}"


def companion(script: dict[str, list]) -> None:
    register("companion", keyed_client(script), ["delegate_to_agent"])


def specialist(name: str, *objectives: str, tools=(), then=None) -> dict[str, list]:
    """Register `name` and return script rows for each objective it is delegated."""
    rows = {brief(o): [(f"{name} did {o}", None)] for o in objectives}
    register(name, keyed_client(then or rows), list(tools))
    return rows


def done(ledger: list[dict]) -> list[tuple[str, str]]:
    return [(e["agent"], e["status"]) for e in ledger]


async def test_two_delegates_in_one_turn_give_total_two_and_two_done_entries():
    specialist("calendar", "look")
    specialist("messenger", "draft")
    companion(
        {
            "go": [
                (None, [delegate("c1", "calendar", "look")]),
                (None, [delegate("c2", "messenger", "draft")]),
                ("All done.", None),
            ]
        }
    )
    graph = h.compiled_graph([SubTask("companion", "go")])
    out = await graph.ainvoke(h.graph_input("go"), h.thread_config())
    assert out["conductor_delegate_total"] == 2
    assert done(out["conductor_ledgers"][0]) == [
        ("calendar", "done"),
        ("messenger", "done"),
    ]
    trace = out.get("message_trace")
    if trace is not None:
        assert done(trace.conductor_ledger) == done(out["conductor_ledgers"][0])


async def test_a_parked_delegate_resumes_to_one_ledger_entry_and_total_one():
    specialist(
        "messenger",
        then={
            brief("send"): [
                (None, [h.tc("s1", "send_email", to="ana", body="hi")]),
                ("Sent.", None),
            ]
        },
        tools=["send_email"],
    )
    companion(
        {
            "go": [
                (None, [delegate("c1", "messenger", "send")]),
                ("Sent it.", None),
            ]
        }
    )
    graph = h.compiled_graph([SubTask("companion", "go")])
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    paused = (await graph.aget_state(cfg)).values
    assert paused["conductor_delegate_total"] == 1
    assert done(paused["conductor_ledgers"][0]) == [
        ("messenger", "awaiting_confirmation")
    ]

    out = await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)

    assert out["conductor_delegate_total"] == 1
    assert done(out["conductor_ledgers"][0]) == [("messenger", "done")]
    assert [c[0] for c in h.calls] == ["send_email"]


async def test_compound_ledgers_concatenate_in_subtask_order_and_counts_sum():
    specialist("calendar", "look")
    specialist("messenger", "draft")
    companion(
        {
            "S0": [(None, [delegate("c1", "calendar", "look")]), ("one", None)],
            "S1": [(None, [delegate("c2", "messenger", "draft")]), ("two", None)],
        }
    )
    graph = h.compiled_graph(
        [SubTask("companion", "S0"), SubTask("companion", "S1")], compound=True
    )
    out = await graph.ainvoke(h.graph_input("go"), h.thread_config())
    assert [done(ledger) for ledger in out["conductor_ledgers"]] == [
        [("calendar", "done")],
        [("messenger", "done")],
    ]
    assert out["conductor_delegate_total"] == 2
    assert out["conductor_delegate_counts"] == {"calendar": 1, "messenger": 1}


def _refusals(out: dict) -> int:
    return sum(
        1
        for ledger in out["conductor_ledgers"]
        for entry in ledger
        if entry["status"] == "ask_user"
    )


async def test_subtasks_together_reach_the_turn_cap():
    names = ["a", "b", "c", "d"]
    for n in names:
        specialist(n, "x")
    s0 = [(None, [delegate(f"0{n}", n, "x")]) for n in names[:3]] + [("end0", None)]
    s1 = [(None, [delegate(f"1{n}", n, "x")]) for n in names] + [("end1", None)]
    companion({"S0": s0, "S1": s1})
    graph = h.compiled_graph(
        [SubTask("companion", "S0"), SubTask("companion", "S1")], compound=True
    )
    out = await graph.ainvoke(h.graph_input("go"), h.thread_config())
    assert DELEGATE_TURN_CAP == 6
    assert out["conductor_delegate_total"] == DELEGATE_TURN_CAP
    assert _refusals(out) == 1


async def test_the_per_specialist_cap_counts_across_subtasks():
    specialist("a", "x", "y", "z")
    s0 = [(None, [delegate("0a", "a", "x")]), ("end0", None)]
    s1 = [
        (None, [delegate("1a", "a", "y")]),
        (None, [delegate("1b", "a", "z")]),
        ("end1", None),
    ]
    companion({"S0": s0, "S1": s1})
    graph = h.compiled_graph(
        [SubTask("companion", "S0"), SubTask("companion", "S1")], compound=True
    )
    out = await graph.ainvoke(h.graph_input("go"), h.thread_config())
    assert out["conductor_delegate_counts"] == {"a": 2}
    assert _refusals(out) == 1


async def test_totals_hold_when_one_subtask_pauses_and_resumes():
    specialist(
        "messenger",
        then={
            brief("send"): [
                (None, [h.tc("s1", "send_email", to="ana", body="hi")]),
                ("Sent.", None),
            ]
        },
        tools=["send_email"],
    )
    specialist("calendar", "look")
    companion(
        {
            "S0": [(None, [delegate("c1", "messenger", "send")]), ("one", None)],
            "S1": [(None, [delegate("c2", "calendar", "look")]), ("two", None)],
        }
    )
    graph = h.compiled_graph(
        [SubTask("companion", "S0"), SubTask("companion", "S1")], compound=True
    )
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("go"), cfg)
    paused = (await graph.aget_state(cfg)).values
    assert paused["conductor_delegate_total"] == 2

    out = await graph.ainvoke(Command(resume={"choice": "approve"}), cfg)

    assert out["conductor_delegate_total"] == 2
    assert [done(ledger) for ledger in out["conductor_ledgers"]] == [
        [("messenger", "done")],
        [("calendar", "done")],
    ]


async def test_only_subtask_two_delegating_pads_the_ledgers():
    register("plain", keyed_client({"P0": [("p0", None)], "P1": [("p1", None)]}), [])
    specialist("calendar", "look")
    companion({"S2": [(None, [delegate("c1", "calendar", "look")]), ("two", None)]})

    async def routing_slot(state, config=None):
        return {"conductor_ledgers": [[]]}

    graph = h.compiled_graph(
        [SubTask("plain", "P0"), SubTask("plain", "P1"), SubTask("companion", "S2")],
        compound=True,
        overrides={"decompose": routing_slot},
    )
    out = await graph.ainvoke(h.graph_input("go"), h.thread_config())
    assert [done(ledger) for ledger in out["conductor_ledgers"]] == [
        [],
        [],
        [("calendar", "done")],
    ]
