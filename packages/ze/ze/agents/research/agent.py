from typing import AsyncIterator

from tavily import AsyncTavilyClient

from ze.agents.base import BaseAgent
from ze_core.orchestration.registry import agent
from ze.agents.research.tools import format_search_results
from ze.agents.types import AgentContext, AgentResult
from ze.openrouter.client import OpenRouterClient
from ze.settings import Settings
from ze.tools.facts import to_user_facts
from ze_core.capability.types import Mode

_AGENT_INSTRUCTIONS = """\
You are Ze's research capability. Use web search to find accurate, up-to-date information.

- Always search before answering questions about current events, facts, or anything that may have changed.
- Summarize sources clearly and cite them when relevant.
- If search results are insufficient, say so rather than guessing.
- Never fabricate URLs or quotes.\
"""


@agent
class ResearchAgent(BaseAgent):
    name = "research"
    description = """
      Handles web searches, fact-finding, summarisation, and research synthesis.
      Use when the user explicitly says "research", "look up", "find out", "search for",
      or asks about current events, factual lookups, topic deep-dives, company or
      organisation history, news, or anything requiring information retrieval from the web.
      Also use for factual comparisons ("what are the differences between X and Y"),
      technical how-things-work questions, and any query where accurate sourced information
      matters more than reasoning or conversation.
    """
    model = "anthropic/claude-sonnet-4-5"
    model_simple = "anthropic/claude-haiku-4-5"
    vision_capable = True
    timeout = 30
    tools = ["web_search", "extract_facts"]
    intent_map = {"read": "web_search"}
    capabilities = {
        "read": Mode.AUTONOMOUS,
        "execute": Mode.CONFIRM,
        "create": Mode.AUTONOMOUS,
        "update": Mode.AUTONOMOUS,
        "delete": Mode.AUTONOMOUS,
        "reason": Mode.AUTONOMOUS,
    }

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        tavily_client: AsyncTavilyClient,
        settings: Settings,
    ) -> None:
        super().__init__(settings)
        self._client = openrouter_client
        self._tavily = tavily_client

    async def run(self, ctx: AgentContext) -> AgentResult:
        await self.emit(ctx, "research.searching")
        system = self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx)
        response, loop_tool_calls = await self.agentic_loop(
            ctx,
            client=self._client,
            messages=list(ctx.messages),
            system=system,
            deps={"client": self._tavily},
            tool_names=["web_search"],
        )

        await self.emit(ctx, "research.summarising")
        facts_tc = await self.call_tool(
            "extract_facts", ctx,
            prompt=ctx.prompt,
            response=response,
            client=self._client,
            model=self._model(ctx),
        )

        proposals = to_user_facts(facts_tc.result or [])
        search_count = len([tc for tc in loop_tool_calls if tc.tool_name == "web_search"])

        self._log.info(
            "research_agent_complete",
            session_id=ctx.session_id,
            search_count=search_count,
            proposals=len(proposals),
        )

        return AgentResult(
            agent=self.name,
            response=response,
            tool_calls=loop_tool_calls + [facts_tc],
            memory_proposals=proposals,
        )

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        search_tc = await self.call_tool(
            "web_search", ctx, query=ctx.prompt, client=self._tavily
        )
        augmented = f"{ctx.prompt}\n\nSearch results:\n{format_search_results(search_tc)}"
        messages = ctx.messages[:-1] + [{"role": "user", "content": augmented}]
        async for token in self._client.stream(
            messages=messages,
            model=self._model(ctx),
            system=self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx),
        ):
            yield token
