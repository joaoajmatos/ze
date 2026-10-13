"""`call_tool` carries the undo payload and applies the one retry policy (Phase 180)."""

from __future__ import annotations

import pytest

from ze_agents.base_agent import RETRY_WRITE_REFUSAL, BaseAgent
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, clear_tool_registry, tool, undo_payload
from ze_agents.types import AgentContext, AgentResult


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


def _agent() -> BaseAgent:
    class _A(BaseAgent):
        name = "owner"
        description = "d"
        tools = []

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="ok")

    return _A()


def _ctx(retry: bool = False) -> AgentContext:
    return AgentContext(session_id="s1", prompt="hi", intent="write", retry_mode=retry)


def _reversible(name: str, result):
    async def _impl() -> dict:
        return result

    _impl.__name__ = name
    tool(
        access=ToolAccess.WRITE,
        description=name,
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="undoer",
        undo_note="n",
    )(_impl)


def _undoer() -> None:
    async def undoer() -> dict:
        return {"ok": True}

    tool(
        access=ToolAccess.WRITE,
        description="u",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )(undoer)


async def test_payload_popped_into_tool_call_undo():
    _undoer()
    _reversible("make", {"ok": True, "id": "1", "undo": undo_payload(thing_id="1")})
    tc = await _agent().call_tool("make", _ctx())
    assert tc.undo == {"thing_id": "1"}
    assert tc.result == {"ok": True, "id": "1"}
    assert tc.agent == "owner"


async def test_reversible_without_payload_has_none():
    _undoer()
    _reversible("make", {"ok": True})
    tc = await _agent().call_tool("make", _ctx())
    assert tc.undo is None


async def test_payload_dropped_from_irreversible_tool():
    @tool(
        access=ToolAccess.WRITE,
        description="w",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )
    async def send() -> dict:
        return {"ok": True, "undo": {"x": 1}}

    tc = await _agent().call_tool("send", _ctx())
    assert tc.undo is None
    assert tc.result == {"ok": True}


async def test_payload_dropped_from_read_tool():
    @tool(access=ToolAccess.READ, description="r")
    async def look() -> dict:
        return {"v": 1, "undo": {"x": 1}}

    tc = await _agent().call_tool("look", _ctx())
    assert tc.undo is None
    assert tc.result == {"v": 1}


@pytest.mark.parametrize(
    "result",
    [
        {"error": "bad", "undo": {"a": 1}},
        {"ok": False, "undo": {"a": 1}},
        {"status": "error", "undo": {"a": 1}},
    ],
)
async def test_payload_dropped_from_error_result(result):
    _undoer()
    _reversible("make", result)
    tc = await _agent().call_tool("make", _ctx())
    assert tc.undo is None
    assert "undo" not in tc.result


async def test_payload_dropped_when_tool_raises():
    _undoer()

    @tool(
        access=ToolAccess.WRITE,
        description="r",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="undoer",
        undo_note="n",
    )
    async def boom() -> dict:
        raise RuntimeError("x")

    tc = await _agent().call_tool("boom", _ctx())
    assert tc.success is False
    assert tc.undo is None
    assert tc.agent == "owner"


async def test_non_dict_result_has_no_undo():
    _undoer()

    @tool(
        access=ToolAccess.WRITE,
        description="r",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="undoer",
        undo_note="n",
    )
    async def text() -> str:
        return "done"

    tc = await _agent().call_tool("text", _ctx())
    assert tc.undo is None
    assert tc.result == "done"


async def test_agent_set_on_retry_refusal():
    @tool(
        access=ToolAccess.WRITE,
        description="w",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )
    async def send() -> str:
        return "sent"

    tc = await _agent().call_tool("send", _ctx(True))
    assert tc.agent == "owner"
    assert tc.gate == "denied"
    assert tc.result == RETRY_WRITE_REFUSAL


async def test_retry_mode_runs_reversible_write():
    _undoer()
    _reversible("make", {"ok": True, "undo": undo_payload(thing_id="2")})
    tc = await _agent().call_tool("make", _ctx(True))
    assert tc.success is True
    assert tc.undo == {"thing_id": "2"}


async def test_retry_mode_refuses_irreversible_write():
    ran = []

    @tool(
        access=ToolAccess.WRITE,
        description="w",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )
    async def send() -> str:
        ran.append(1)
        return "sent"

    tc = await _agent().call_tool("send", _ctx(True))
    assert ran == []
    assert tc.success is False
