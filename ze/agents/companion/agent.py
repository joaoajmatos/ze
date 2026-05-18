from typing import AsyncIterator

from ze.agents.base import BaseAgent
from ze.agents.companion.prompt import SYSTEM_PROMPT
from ze.agents.registry import register
from ze.agents.types import AgentContext, AgentResult
from ze.openrouter.client import OpenRouterClient
from ze.settings import Settings


@register
class CompanionAgent(BaseAgent):
    name  = "companion"
    tools: list[str] = []

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

        self._log.info("companion_agent_complete", session_id=ctx.session_id)

        return AgentResult(agent=self.name, response=response, tool_calls=[])

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        async for token in self._client.stream(
            messages=[{"role": "user", "content": ctx.prompt}],
            model=self._model(),
            system=SYSTEM_PROMPT.format(memory_context=self._format_memory(ctx)),
        ):
            yield token
