"""In-node workspace confirm resume. Must not import ze_workspace."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.errors import ToolConfirmationRequired
from ze_agents.interrupt import tool_interrupt_fn
from ze_agents.registry import clear_registry
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult, GateDecision
from ze_core.conversation.turn import _interrupt_payload, resume_turn


@pytest.fixture(autouse=True)
def _clean_tools():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


def test_this_module_does_not_import_ze_workspace():
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith("ze_workspace") for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("ze_workspace")


def _agent() -> BaseAgent:
    class _A(BaseAgent):
        name = "test"
        description = "test"
        tools = ["workspace_write"]

        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=self.name, response="ok")

    return _A()


def _ctx() -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt="write",
        intent="write",
        gate_decision=GateDecision.EXECUTE,
    )


async def test_approve_executes_edited_payload():
    sidecar = AsyncMock()
    calls: list[str] = []

    @tool(access=ToolAccess.WRITE, description="write")
    async def workspace_write(path: str, content: str) -> str:
        calls.append(content)
        if len(calls) == 1:
            raise ToolConfirmationRequired(
                "Write file?", editable=True, proposed=content
            )
        await sidecar.put(path, content)
        return f"wrote {content}"

    token = tool_interrupt_fn.set(
        lambda payload: {"choice": "approve", "edited_content": "edited-body"}
    )
    try:
        tc = await _agent().call_tool(
            "workspace_write", _ctx(), path="notes.txt", content="original"
        )
    finally:
        tool_interrupt_fn.reset(token)

    assert tc.success is True
    assert calls == ["original", "edited-body"]
    sidecar.put.assert_awaited_once_with("notes.txt", "edited-body")


async def test_deny_does_not_call_sidecar():
    sidecar = AsyncMock()

    @tool(access=ToolAccess.WRITE, description="write")
    async def workspace_write(path: str, content: str) -> str:
        raise ToolConfirmationRequired("Write file?", editable=True, proposed=content)

    token = tool_interrupt_fn.set(lambda payload: {"choice": "deny"})
    try:
        tc = await _agent().call_tool(
            "workspace_write", _ctx(), path="notes.txt", content="nope"
        )
    finally:
        tool_interrupt_fn.reset(token)

    assert tc.success is False
    assert tc.error == "denied by user"
    sidecar.put.assert_not_awaited()


def test_interrupt_payload_feeds_pending_confirmation_fields():
    interrupt = SimpleNamespace(
        value={"prompt": "Run ls?", "editable": True, "proposed": "ls -la"}
    )
    graph_state = SimpleNamespace(interrupts=[interrupt], tasks=[])
    payload = _interrupt_payload(graph_state)
    assert payload["prompt"] == "Run ls?"
    assert payload["editable"] is True
    assert payload["proposed"] == "ls -la"


async def test_resume_turn_uses_command_resume_when_in_node_interrupt():
    from langgraph.types import Command

    graph = MagicMock()
    graph.aget_state = AsyncMock(
        side_effect=[
            SimpleNamespace(
                interrupts=[
                    SimpleNamespace(value={"prompt": "ok", "editable": True})
                ],
                next=(),
                values={"final_response": "done"},
                tasks=[],
            ),
            SimpleNamespace(interrupts=[], next=(), values={"final_response": "done"}),
        ]
    )
    graph.ainvoke = AsyncMock(return_value={"final_response": "done"})
    container = SimpleNamespace(graph=graph)

    result = await resume_turn(
        container, {"configurable": {"thread_id": "t"}}, resume={"choice": "approve"}
    )
    assert result.response == "done"
    command = graph.ainvoke.await_args.args[0]
    assert isinstance(command, Command)
    assert command.resume == {"choice": "approve"}
