from __future__ import annotations

from typing import AsyncIterator

from sentence_transformers import SentenceTransformer

from ze_agents.base_agent import BaseAgent
from ze_agents.client import LLMClient
from ze_agents.nli import NLIClient
from ze_agents.registry import agent
from ze_agents.types import AgentContext, AgentResult, Intent, Mode
from ze_collision.store import CollisionLogStore

import ze_priority.tools  # noqa: F401 — registers reprioritize_item
from ze_priority.store import PriorityOverrideStore
from ze_priority.view import PriorityView

_AGENT_INSTRUCTIONS = """\
You help the user reprioritize what Ze is currently paying attention to — open
loops, stuck or near-gate goals, and recent hypotheses.

Available tools:
- reprioritize_item: make a named item more urgent or less urgent relative to
  Ze's current ranking (item_description, requested_relation: more_urgent or
  less_urgent, pin: true only if the user clearly wants this to stick permanently)

Guidelines:
- Restate which item you identified and the requested change before it takes effect.
- If the tool asks for clarification (ambiguous or no match), ask the user to
  narrow it down rather than guessing.
- If the tool reports the instruction could not be applied, tell the user plainly —
  never report success when the underlying write failed.\
"""


@agent
class PriorityAgent(BaseAgent):
    name = "priority"
    display_name = "Priority"
    description = """
      Reprioritizing what Ze currently thinks matters most — open loops, stuck
      goals, and hypotheses.
      Use for: "that can wait", "make X more urgent", "deprioritize the Y goal",
      "focus on X instead", "bump X to the top", "X isn't important right now".
      Not for creating, closing, or editing the underlying loop/goal/hypothesis
      itself — only for reordering attention among existing ones.
    """
    model = "anthropic/claude-haiku-4-5"
    timeout = 30
    tools = ["reprioritize_item"]
    intents = {
        "update": Intent(
            Mode.CONFIRM, "Reprioritize an item — make it more or less urgent."
        ),
    }

    def __init__(
        self,
        openrouter_client: LLMClient,
        priority_view: PriorityView,
        override_store: PriorityOverrideStore,
        collision_store: CollisionLogStore,
        nli_client: NLIClient,
        embedder: SentenceTransformer,
    ) -> None:
        self._client = openrouter_client
        self._priority_view = priority_view
        self._override_store = override_store
        self._collision_store = collision_store
        self._nli_client = nli_client
        self._embedder = embedder

    async def run(self, ctx: AgentContext) -> AgentResult:
        await self.emit(ctx, "priority.reprioritizing")
        system = self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx)
        response, loop_tool_calls = await self.agentic_loop(
            ctx,
            client=self._client,
            messages=list(ctx.messages),
            system=system,
            deps={
                "priority_view": self._priority_view,
                "override_store": self._override_store,
                "collision_store": self._collision_store,
                "nli_client": self._nli_client,
                "embedder": self._embedder,
            },
        )
        return AgentResult(
            agent=self.name, response=response, tool_calls=loop_tool_calls
        )

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        result = await self.run(ctx)
        yield result.response
