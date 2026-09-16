from __future__ import annotations

from typing import AsyncIterator

from ze_agents.base_agent import BaseAgent
from ze_agents.client import LLMClient
from ze_agents.nested_tools import enforce_domain_cancel_confirmations
from ze_agents.registry import agent
from ze_agents.types import AgentContext, AgentResult, Intent, Mode
from ze_worldstate.store import LoopStore
import ze_worldstate.agents.tools  # noqa: F401

_AGENT_INSTRUCTIONS = """\
You manage the user's lingering open loops (concerns without a fire time).

Available tools:
- list_open_loops: pending/suspected/active/drifting loops (id, title, state)
- close_loop: close a loop by id when the concern is resolved
- drop_loop: drop a loop by id when the user wants it gone

When the user says forget/drop/close a concern:
- Call list_open_loops first.
- Match the unique title. If two titles share the query, ask which one. If none match, say so.
- Call close_loop or drop_loop at most once, only on a unique match. Never batch.
- Do not claim a loop is closed or dropped unless that tool succeeded this turn.
"""


@agent
class LoopsAgent(BaseAgent):
    name = "loops"
    display_name = "Open loops"
    description = """
      Lingering concerns and open loops without a timed reminder.
      Use for: "forget that job-switch worry", "close the loop about X",
      "drop the concern about Y", "what am I still sitting with".
      Not for timed reminders, biography facts, or multi-week goals.
    """
    model = "anthropic/claude-haiku-4-5"
    vision_capable = False
    timeout = 15
    tools = ["list_open_loops", "close_loop", "drop_loop"]
    intents = {
        "manage": Intent(Mode.AUTONOMOUS, "List, close, or drop an open loop."),
    }
    default_mode = Mode.AUTONOMOUS

    def __init__(self, openrouter_client: LLMClient, loop_store: LoopStore) -> None:
        self._client = openrouter_client
        self._store = loop_store

    async def run(self, ctx: AgentContext) -> AgentResult:
        system = self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx)
        original_sink = ctx.token_sink

        async def _buffer(_chunk: str) -> None:
            return None

        if original_sink is not None:
            ctx.token_sink = _buffer
        try:
            response, loop_tool_calls = await self.agentic_loop(
                ctx,
                client=self._client,
                messages=list(ctx.messages),
                system=system,
                deps={"loop_store": self._store},
            )
        finally:
            ctx.token_sink = original_sink
        gated = enforce_domain_cancel_confirmations(response, loop_tool_calls)
        if original_sink is not None:
            await original_sink(gated)
        return AgentResult(agent=self.name, response=gated, tool_calls=loop_tool_calls)

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        result = await self.run(ctx)
        yield result.response
