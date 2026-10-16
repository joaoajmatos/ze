"""Resolution order of `BaseAgent.call_tool` for asks-first tools (Phase 181, D1)."""

from __future__ import annotations

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import AgentConfigError
from ze_agents.park import OVER_CAP_RESULT
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import AskDecision, ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult

calls: list[tuple[str, dict]] = []


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    calls.clear()
    yield
    clear_registry()
    clear_tool_registry()


class _Agent(BaseAgent):
    name = "calendar"
    description = "test"

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, response="ok")


def _ctx(**kw) -> AgentContext:
    base = dict(session_id="s", prompt="p", loop_active=True)
    base.update(kw)
    return AgentContext(**base)


def _irreversible(name: str, **kw):
    async def _impl(event_id: str = "", body: str = "") -> str:
        calls.append((name, {"event_id": event_id, "body": body}))
        return "done"

    _impl.__name__ = name
    tool(
        access=ToolAccess.WRITE,
        description=name,
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="deleted a calendar event",
        **kw,
    )(_impl)


async def test_asks_first_parks_without_running() -> None:
    _irreversible("delete_event")
    tc = await _Agent().call_tool(
        "delete_event",
        _ctx(),
        _lm_args={"event_id": "e1"},
        _call_id="c1",
        event_id="e1",
    )
    assert calls == []
    assert tc.gate == "parked" and tc.success is False
    pw = tc.parked
    assert pw is not None
    assert (pw.tool, pw.args, pw.call_id, pw.agent) == (
        "delete_event",
        {"event_id": "e1"},
        "c1",
        "calendar",
    )
    assert pw.effect_phrase == "deleted a calendar event"
    assert pw.reason == "asks_first"
    assert pw.summary == "event_id: e1"
    assert pw.item_id


async def test_summarize_and_editable_field_used() -> None:
    _irreversible("send_email", summarize=lambda a: "to Ana", editable_field="body")
    tc = await _Agent().call_tool(
        "send_email", _ctx(), _lm_args={"body": "hi"}, _call_id="c1", body="hi"
    )
    assert tc.parked.summary == "to Ana"
    assert tc.parked.editable_field == "body"


async def test_approved_call_id_runs() -> None:
    _irreversible("delete_event")
    tc = await _Agent().call_tool(
        "delete_event",
        _ctx(),
        _lm_args={"event_id": "e1"},
        _approved_call_id="c1",
        event_id="e1",
    )
    assert calls == [("delete_event", {"event_id": "e1", "body": ""})]
    assert tc.gate == "approved" and tc.success


async def test_pre_approved_writes_run_with_gate() -> None:
    _irreversible("delete_event")
    ctx = _ctx(pre_approved_writes=frozenset({"delete_event"}))
    tc = await _Agent().call_tool("delete_event", ctx, _lm_args={}, event_id="e1")
    assert calls and tc.gate == "pre_approved"
    assert tc.approval == {"outcome": "pre_approved"}


async def test_retry_mode_refuses_before_parking() -> None:
    _irreversible("delete_event")
    tc = await _Agent().call_tool("delete_event", _ctx(retry_mode=True), event_id="e1")
    assert calls == []
    assert tc.parked is None and tc.gate == "denied"


async def test_opt_out_runs() -> None:
    _irreversible("ingest_text", asks_first=False, no_ask_reason="saves only")
    tc = await _Agent().call_tool("ingest_text", _ctx(), event_id="e1")
    assert calls and tc.gate == "none"


async def test_reversible_runs() -> None:
    async def _impl() -> str:
        calls.append(("create_event", {}))
        return "ok"

    _impl.__name__ = "create_event"
    tool(
        access=ToolAccess.WRITE,
        description="d",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="delete_event",
        undo_note="n",
        effect_phrase="created",
    )(_impl)
    tc = await _Agent().call_tool("create_event", _ctx())
    assert calls and tc.success


async def test_ask_check_ask_run_refuse() -> None:
    decision = {"d": AskDecision.ask("because")}
    _irreversible(
        "ws_write",
        asks_first=False,
        no_ask_reason="gate decides",
        ask_check=lambda a, c: decision["d"],
    )
    tc = await _Agent().call_tool("ws_write", _ctx(), _lm_args={}, _call_id="c1")
    assert tc.gate == "parked" and tc.parked.reason == "check"
    assert calls == []

    decision["d"] = AskDecision.run()
    tc = await _Agent().call_tool("ws_write", _ctx())
    assert tc.success and calls

    decision["d"] = AskDecision.refuse("no way")
    calls.clear()
    tc = await _Agent().call_tool("ws_write", _ctx())
    assert calls == [] and tc.parked is None
    assert tc.result == "no way" and tc.gate == "denied"


async def test_round_cap_refuses() -> None:
    _irreversible("delete_event")
    tc = await _Agent().call_tool(
        "delete_event", _ctx(write_round=3), _lm_args={}, _call_id="c1", event_id="e1"
    )
    assert calls == []
    assert tc.parked is None
    assert tc.gate == "refused_over_cap"
    assert tc.result == OVER_CAP_RESULT


async def test_asks_first_outside_loop_is_a_config_error() -> None:
    _irreversible("delete_event")
    with pytest.raises(AgentConfigError, match="outside the agent loop"):
        await _Agent().call_tool("delete_event", _ctx(loop_active=False), event_id="e1")
    assert calls == []
