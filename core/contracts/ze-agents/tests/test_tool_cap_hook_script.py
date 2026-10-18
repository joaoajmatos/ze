"""The tool-call cap does not count a script's inner reads, but counts its writes (197)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import HookAbort
from ze_agents.hooks import ToolStartEvent, clear_hooks, register_hook
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.scripts import ScriptOutcome, ScriptRequest, in_script_call
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.tool_cap_hook import ToolCallCapHook
from ze_agents.types import AgentContext, AgentResult

wrote: list[str] = []


@pytest.fixture(autouse=True)
def clean():
    for fn in (clear_registry, clear_tool_registry, clear_hooks):
        fn()
    wrote.clear()

    @tool(access=ToolAccess.READ, description="rows")
    async def get_rows() -> str:
        return "{}"

    @tool(
        access=ToolAccess.WRITE,
        description="note",
        reversibility=ToolReversibility.IRREVERSIBLE,
        asks_first=False,
        no_ask_reason="test",
    )
    async def save_note(text: str = "") -> str:
        wrote.append(text)
        return "saved"

    yield
    for fn in (clear_registry, clear_tool_registry, clear_hooks):
        fn()


class _Agent(BaseAgent):
    name = "finance"
    description = "t"
    tools = ["get_rows", "save_note"]

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, response="ok")


class _Runner:
    def __init__(self, reads: int, writes: list[dict]):
        self.reads = reads
        self.writes = writes

    async def run(
        self, *, script_id, agent, source, stub, limits, dispatch, procedure_id=None, context=None
    ):
        for i in range(self.reads):
            await dispatch(ScriptRequest(seq=i, tool="get_rows", args={}))
        return ScriptOutcome(status="ok", value={"n": self.reads}, writes=self.writes)


async def test_hook_skips_calls_made_inside_a_script() -> None:
    hook = ToolCallCapHook(max_tool_calls=1)
    ctx = AgentContext(session_id="s", prompt="p")
    token = in_script_call.set(True)
    try:
        for _ in range(5):
            await hook.on_tool_start(ToolStartEvent("get_rows", {}, ctx, 0))
    finally:
        in_script_call.reset(token)
    await hook.on_tool_start(ToolStartEvent("get_rows", {}, ctx, 0))
    with pytest.raises(HookAbort):
        await hook.on_tool_start(ToolStartEvent("get_rows", {}, ctx, 0))


async def test_twenty_reads_then_a_write_still_reaches_the_write_gate() -> None:
    register_hook(ToolCallCapHook(max_tool_calls=20))
    ctx = AgentContext(session_id="s", prompt="p")
    ctx.script_runner = _Runner(20, [{"tool": "save_note", "args": {"text": "hi"}}])
    client = MagicMock()
    client.complete_with_tools = AsyncMock(
        side_effect=[
            (
                None,
                [{"id": "c1", "name": "run_tool_script", "arguments": {"source": "x"}}],
            ),
            ("done", None),
        ]
    )
    _, calls = await _Agent().agentic_loop(ctx, client, [], system="s")
    assert wrote == ["hi"]
    step = calls[0]
    assert len(step.inner_calls) == 20
    assert all(c.success for c in step.inner_calls)
    write = [c for c in calls if c.tool_name == "save_note"][0]
    assert write.success is True and write.parent_call_id == step.call_id
