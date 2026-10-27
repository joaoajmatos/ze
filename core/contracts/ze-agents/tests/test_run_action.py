"""`BaseAgent.run_action` runs a screen-pressed tool action through `call_tool` (Phase 191a)."""

from __future__ import annotations

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import UiActionRefusedError
from ze_agents.hooks import HarnessHook, clear_hooks, register_hook
from ze_agents.park import ApprovedCall
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import AskDecision, Injected, ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult, WriteGateState

calls: list[tuple[str, dict]] = []


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    clear_hooks()
    calls.clear()
    yield
    clear_registry()
    clear_tool_registry()
    clear_hooks()


class _Store:
    pass


class _Agent(BaseAgent):
    name = "news"
    description = "test"
    tools: list[str] = []

    def tool_deps(self) -> dict:
        return {"store": _Store()}

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, response="ok")


_GATE_KW = {
    "resume": "resume",
    "write_decisions": "decisions",
    "pre_approved_writes": "pre_approved",
    "write_round": "round",
    "approval_request_id": "approval_request_id",
    "loop_active": "loop_active",
    "retry_mode": "retry_mode",
}


def _gate(kw: dict, **defaults) -> dict:
    """Fold the write-gate keyword names a test passes into one `WriteGateState`."""
    gate = {_GATE_KW[k]: kw.pop(k) for k in list(kw) if k in _GATE_KW}
    return {"write_gate": WriteGateState(**{**defaults, **gate}), **kw}


def _ctx(**kw) -> AgentContext:
    return AgentContext(session_id="s", prompt="", **_gate(kw))


def _irreversible(name: str = "archive_source", **kw):
    async def _impl(source_id: str, store: _Store, count: int = 1) -> str:
        calls.append((name, {"source_id": source_id, "count": count}))
        return "done"

    _impl.__name__ = name
    tool(
        access=ToolAccess.WRITE,
        description=name,
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="archived a source",
        ui_action=True,
        **kw,
    )(_impl)


def _reversible(name: str = "mark_read"):
    async def _impl(source_id: str, store: _Store) -> str:
        calls.append((name, {"source_id": source_id}))
        return "done"

    _impl.__name__ = name
    tool(
        access=ToolAccess.WRITE,
        description=name,
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="archive_source",
        undo_note="Mark unread",
        effect_phrase="marked a source as read",
        ui_action=True,
    )(_impl)


async def test_asks_first_tool_parks_with_full_item() -> None:
    _irreversible()
    ctx = _ctx()
    tc = await _Agent().run_action("archive_source", {"source_id": "s1"}, ctx)
    assert calls == []
    assert tc.gate == "parked" and tc.success is False
    pw = tc.parked
    assert pw is not None
    assert pw.call_id and pw.item_id
    assert pw.summary == "source_id: s1"
    assert pw.effect_phrase == "archived a source"
    assert (pw.tool, pw.args, pw.agent) == (
        "archive_source",
        {"source_id": "s1"},
        "news",
    )


async def test_approved_call_runs_once_and_records_request() -> None:
    _irreversible()
    agent = _Agent()
    parked = (
        await agent.run_action("archive_source", {"source_id": "s1"}, _ctx())
    ).parked
    tc = await agent.run_action(
        "archive_source",
        {"source_id": "s1"},
        _ctx(),
        approval=ApprovedCall(parked.call_id),
        approval_request_id="r1",
    )
    assert calls == [("archive_source", {"source_id": "s1", "count": 1})]
    assert tc.success is True and tc.gate == "approved"
    assert tc.approval == {"request_id": "r1", "outcome": "approved"}


async def test_reversible_write_runs_and_restores_loop_active() -> None:
    _reversible()
    ctx = _ctx(loop_active=False)
    tc = await _Agent().run_action("mark_read", {"source_id": "s1"}, ctx)
    assert tc.success is True
    assert calls == [("mark_read", {"source_id": "s1"})]
    assert ctx.write_gate.loop_active is False

    ctx2 = _ctx(loop_active=True)
    await _Agent().run_action("mark_read", {"source_id": "s2"}, ctx2)
    assert ctx2.write_gate.loop_active is True


async def test_loop_active_restored_when_the_tool_raises() -> None:
    async def boom(source_id: str) -> str:
        raise RuntimeError("x")

    tool(
        access=ToolAccess.WRITE,
        description="b",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="boom",
        undo_note="n",
        ui_action=True,
    )(boom)
    ctx = _ctx()
    tc = await _Agent().run_action("boom", {"source_id": "s"}, ctx)
    assert tc.success is False
    assert ctx.write_gate.loop_active is False


async def test_constraint_veto_still_applies() -> None:
    _reversible()

    class _Veto(HarnessHook):
        async def check_call(self, event):
            return AskDecision.refuse("blocked by a constraint")

    register_hook(_Veto())
    # constraint_gate must be on for the hook to be consulted
    from ze_agents.tool import get_tool

    get_tool("mark_read").constraint_gate = True
    tc = await _Agent().run_action("mark_read", {"source_id": "s1"}, _ctx())
    assert calls == []
    assert tc.success is False


@pytest.mark.parametrize(
    "args",
    [
        {"source_id": "s1", "_approval": "x"},
        {"source_id": "s1", "ctx": "x"},
        {"source_id": "s1", "store": "x"},
        {"source_id": "s1", "extra": "x"},
        {"source_id": ["a"]},
        {"source_id": {"a": 1}},
        {"source_id": 5},
        {"source_id": "s1", "count": "many"},
        {"source_id": "s1", "count": True},
        {"source_id": None},
        {"source_id": "s1", "count": None},
        {},
    ],
)
async def test_bad_args_are_refused_and_the_tool_never_runs(args) -> None:
    _irreversible()
    with pytest.raises(UiActionRefusedError):
        await _Agent().run_action(
            "archive_source", args, _ctx(), approval=ApprovedCall("c1")
        )
    assert calls == []


async def test_injected_parameter_is_refused() -> None:
    async def tagged(source_id: str, tag: Injected[str | None] = None) -> str:
        calls.append(("tagged", {"tag": tag}))
        return "ok"

    tool(
        access=ToolAccess.WRITE,
        description="t",
        reversibility=ToolReversibility.REVERSIBLE,
        undo_tool="tagged",
        undo_note="n",
        ui_action=True,
    )(tagged)
    with pytest.raises(UiActionRefusedError):
        await _Agent().run_action("tagged", {"source_id": "s", "tag": "x"}, _ctx())
    assert calls == []


async def test_non_ui_action_or_read_tool_is_refused() -> None:
    async def internal(source_id: str) -> str:
        return "ok"

    tool(
        access=ToolAccess.WRITE,
        description="i",
        reversibility=ToolReversibility.IRREVERSIBLE,
    )(internal)

    async def look(source_id: str) -> str:
        return "ok"

    tool(access=ToolAccess.READ, description="l")(look)
    for name in ("internal", "look", "missing"):
        with pytest.raises(UiActionRefusedError):
            await _Agent().run_action(name, {"source_id": "s"}, _ctx())
