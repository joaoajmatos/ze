from typing import AsyncIterator

from ze.agents.base import BaseAgent
from ze.agents.email.prompt import SYSTEM_PROMPT
from ze.agents.registry import register
from ze.agents.types import AgentContext, AgentResult
from ze.google.auth import GoogleCredentials
from ze.openrouter.client import OpenRouterClient
from ze.settings import Settings
from ze.tools.facts import to_user_facts


@register
class EmailAgent(BaseAgent):
    name  = "email"
    tools = ["list_emails", "get_email", "draft_email", "send_email", "archive_email", "extract_facts"]

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        google_credentials: GoogleCredentials,
        settings: Settings,
    ) -> None:
        super().__init__(settings)
        self._client = openrouter_client
        self._creds  = google_credentials

    async def run(self, ctx: AgentContext) -> AgentResult:
        inbox_tc = await self.call_tool(
            "list_emails", ctx, credentials=self._creds
        )

        augmented = ctx.prompt
        if inbox_tc.success and inbox_tc.result:
            augmented = f"{ctx.prompt}\n\nRecent emails:\n{inbox_tc.result}"

        response = await self._client.complete(
            messages=[{"role": "user", "content": augmented}],
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

        proposals = to_user_facts(facts_tc.result or [])

        self._log.info(
            "email_agent_complete",
            session_id=ctx.session_id,
            emails_fetched=len(inbox_tc.result or []),
            proposals=len(proposals),
        )

        return AgentResult(
            agent=self.name,
            response=response,
            tool_calls=[inbox_tc, facts_tc],
            memory_proposals=proposals,
        )

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        inbox_tc = await self.call_tool(
            "list_emails", ctx, credentials=self._creds
        )
        augmented = ctx.prompt
        if inbox_tc.success and inbox_tc.result:
            augmented = f"{ctx.prompt}\n\nRecent emails:\n{inbox_tc.result}"

        async for token in self._client.stream(
            messages=[{"role": "user", "content": augmented}],
            model=self._model(),
            system=SYSTEM_PROMPT.format(memory_context=self._format_memory(ctx)),
        ):
            yield token
