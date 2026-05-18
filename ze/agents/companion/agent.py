from typing import AsyncIterator

from ze.agents.base import BaseAgent
from ze.agents.companion.prompt import SYSTEM_PROMPT
from ze.agents.registry import register
from ze.agents.types import AgentContext, AgentResult
from ze.memory.types import UserFact
from ze.openrouter.client import OpenRouterClient
from ze.settings import Settings


@register
class CompanionAgent(BaseAgent):
    name  = "companion"
    tools = ["extract_facts"]

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        settings: Settings,
    ) -> None:
        super().__init__(settings)
        self._client = openrouter_client

    async def run(self, ctx: AgentContext) -> AgentResult:
        response = await self._client.complete(
            messages=[{"role": "user", "content": ctx.prompt}],
            model=self._model(),
            system=SYSTEM_PROMPT.format(memory_context=self._format_memory(ctx)),
        )

        facts_tc = await self.call_tool(
            "extract_facts", ctx,
            prompt=ctx.prompt,
            response=response,
            client=self._client,
            model=self._model(),
        )

        proposals = _to_facts(facts_tc.result or [])

        self._log.info(
            "companion_agent_complete",
            session_id=ctx.session_id,
            proposals=len(proposals),
        )

        return AgentResult(
            agent=self.name,
            response=response,
            tool_calls=[facts_tc],
            memory_proposals=proposals,
        )

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        async for token in self._client.stream(
            messages=[{"role": "user", "content": ctx.prompt}],
            model=self._model(),
            system=SYSTEM_PROMPT.format(memory_context=self._format_memory(ctx)),
        ):
            yield token


def _to_facts(raw: list[dict]) -> list[UserFact]:
    return [
        UserFact(
            key=f["key"],
            value=f["value"],
            agent="global",
            confidence=float(f.get("confidence", 0.8)),
        )
        for f in raw
        if isinstance(f, dict) and f.get("key") and f.get("value")
    ]
