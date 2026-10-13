from __future__ import annotations

from typing import AsyncIterator

from ze_agents.base_agent import BaseAgent
from ze_agents.client import LLMClient
from ze_agents.nested_tools import enforce_domain_cancel_confirmations
from ze_agents.registry import agent
from ze_agents.types import AgentContext, AgentResult, Intent, Mode
from ze_worldstate.store import LoopStore
from ze_worldstate.tracking import LoopTracker
import ze_worldstate.agents.tools  # noqa: F401

_AGENT_INSTRUCTIONS = """\
You manage the user's lingering open loops (concerns without a fire time).

Available tools:
- list_open_loops: pending/suspected/active/drifting loops (id, title, state)
- track_loop: start tracking a concern the user explicitly asked you to keep in mind
- close_loop: close a loop by id when the concern is resolved
- drop_loop: drop a loop by id when the user wants it gone

When the user asks you to keep, hold or watch something ("keep it on my radar", "mantém isso no radar"):
- Call track_loop once per distinct concern, with a short title in the user's language (under ten words).
- Do not call it for a worry the user only describes without asking you to hold it.
- Say it is tracked only after track_loop returns ok true this turn. For outcome created or confirmed, say it is now tracked; for reinforced, say it was already tracked; for revived, say it is back on the radar.
- If it returns ok false, say you could not track it and give the reason in one short sentence.
- Never claim you are tracking something without a successful track_loop call this turn.

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
      Use for: "keep the Porto move on my radar", "mantém isso no radar",
      "forget that job-switch worry", "close the loop about X",
      "drop the concern about Y", "what am I still sitting with".
      Not for timed reminders, biography facts, or multi-week goals.
    """
    routing_criteria = """
      Use for: an undecided or worrying matter the user wants held in mind with no date
      ("I haven't decided about X yet, keep it on my radar", "keep an eye on X for me",
      "hold that thought", "mantém X no radar"), and for listing, tracking, closing or
      dropping such a concern
      ("close the worry about X", "fecha a preocupação sobre X").
      Not for: a timed reminder, a multi-week outcome to work towards, or a chat about
      feelings where the user wants to talk it through now.
    """
    model = "anthropic/claude-haiku-4-5"
    vision_capable = False
    timeout = 15
    tools = ["list_open_loops", "track_loop", "close_loop", "drop_loop"]
    intents = {
        "manage": Intent(Mode.AUTONOMOUS, "List, track, close, or drop an open loop."),
    }
    default_mode = Mode.AUTONOMOUS

    def __init__(
        self,
        openrouter_client: LLMClient,
        loop_store: LoopStore,
        loop_tracker: LoopTracker,
    ) -> None:
        self._client = openrouter_client
        self._store = loop_store
        self._tracker = loop_tracker

    def tool_deps(self) -> dict:
        return {"loop_store": self._store, "loop_tracker": self._tracker}

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
                deps=self.tool_deps(),
            )
        finally:
            ctx.token_sink = original_sink
        gated = enforce_domain_cancel_confirmations(
            response, loop_tool_calls, strip_track_claims=True
        )
        if original_sink is not None:
            await original_sink(gated)
        return AgentResult(agent=self.name, response=gated, tool_calls=loop_tool_calls)

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        result = await self.run(ctx)
        yield result.response
