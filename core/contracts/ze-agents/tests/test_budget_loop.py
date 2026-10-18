"""agentic_loop wraps up once the soft deadline has passed."""

from unittest.mock import AsyncMock

from ze_agents.base_agent import BaseAgent
from ze_agents.budget import WRAP_UP_NOTE, set_soft_deadline
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext


async def test_loop_stops_calling_tools_and_answers_after_the_deadline():
    @tool(access=ToolAccess.READ, description="look")
    async def look(q: str) -> str:
        return "found"

    class A(BaseAgent):
        name = "a"
        description = "a"
        tools = ["look"]

        async def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    calls = {"n": 0}

    async def complete_with_tools(**kwargs):
        calls["n"] += 1
        return "", [{"id": "1", "name": "look", "arguments": {"q": "x"}}]

    client = AsyncMock()
    client.complete_with_tools = complete_with_tools
    client.complete = AsyncMock(return_value="Done A, not B. Want me to continue?")
    ctx = AgentContext(session_id="s", prompt="p")
    set_soft_deadline(ctx, -1)

    text, _ = await A().agentic_loop(
        ctx, client=client, messages=[{"role": "user", "content": "p"}], system="s"
    )

    assert text == "Done A, not B. Want me to continue?"
    sent = client.complete.await_args.kwargs["messages"]
    assert sent[-1]["content"] == WRAP_UP_NOTE


def teardown_function():
    clear_tool_registry()
