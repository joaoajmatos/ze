from typing import AsyncIterator

import ze_components.tools  # noqa: F401 — registers render_* tools

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent
from ze_agents.types import AgentContext, AgentResult
from ze_agents.client import LLMClient
from ze_agents.settings import Settings

_AGENT_INSTRUCTIONS = """\
You are Ze's research capability. Use web search to find accurate, up-to-date information.

- Always search before answering questions about current events, facts, or anything that may have changed.
- Summarize sources clearly and cite them when relevant.
- If search results are insufficient, say so rather than guessing.
- Never fabricate URLs or quotes.
- If the question requires calendar data (e.g. "when am I free?", "what's on my schedule?"), \
say you need the calendar agent rather than guessing the schedule.

Showing results:
- Prose is the default. Call a render tool only when the data is tabular or numeric \
and structure helps more than a sentence would, then add one line of context.
- render_table for a comparison of options across several attributes; render_chart \
for numbers over time or across categories. Use only figures from your sources or the \
user's message.
- After a render, always write one short line of takeaway or context that adds something the render does not show (a trend, the largest item, a caveat). Never narrate the tool call and never repeat the rendered numbers in prose.\
"""


@agent
class ResearchAgent(BaseAgent):
    name = "research"
    display_name = "Web research"
    description = """
      Research and technical fact-finding using live web search.
      Use for: what are the differences between X and Y (databases, languages, tools, products),
      how does X work, explain X, find out what changed in the latest release of X,
      coding questions, "look up X", "search for X", "what is X", recent events, and any query
      needing verified facts from the web. Not for calendar, email, reminders, or news digests.
    """
    routing_criteria = """
      Use for: explain a concept, compare options, how-to and step-by-step help,
      recent events and releases, "what is X", technical and factual questions,
      anything that needs a live web search.
      Not for: calendar, email, reminders, or the user's own feelings and decisions.
    """
    model = "anthropic/claude-sonnet-4-5"
    model_simple = "anthropic/claude-haiku-4-5"
    timeout = 90
    tools = ["openrouter:web_search", "render_table", "render_chart"]

    def __init__(
        self,
        openrouter_client: LLMClient,
        settings: Settings,
    ) -> None:
        self._settings = settings
        self._client = openrouter_client

    async def run(self, ctx: AgentContext) -> AgentResult:
        await self.emit(ctx, "research.searching")
        system = self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx)
        response, loop_tool_calls = await self.agentic_loop(
            ctx,
            client=self._client,
            messages=list(ctx.messages),
            system=system,
        )

        search_count = len(
            [tc for tc in loop_tool_calls if tc.tool_name == "openrouter:web_search"]
        )

        self._log.info(
            "research_agent_complete",
            session_id=ctx.session_id,
            search_count=search_count,
        )

        return AgentResult(
            agent=self.name,
            response=response,
            tool_calls=loop_tool_calls,
        )

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        model = self._model(ctx)
        if not model.endswith(":online"):
            model = f"{model}:online"
        async for token in self._client.stream(
            messages=ctx.messages,
            model=model,
            system=self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx),
        ):
            yield token
