import asyncio
import re
from typing import AsyncIterator

import asyncpg

from ze.agents.base import BaseAgent
from ze.agents.registry import register
from ze.agents.types import AgentContext, AgentResult, ToolCall
from ze.contacts.store import PersonStore
from ze.openrouter.client import OpenRouterClient
from ze.settings import Settings
import ze.tools.prospecting  # noqa: F401 — registers log_outreach_event @tool
from ze.tools.contacts import extract_contacts as _  # noqa: F401 — registers @tool
from ze.tools.facts import to_user_facts

_AGENT_INSTRUCTIONS = """\
You reason from what you know and what the user tells you — you do not search the web.
Never label your role or use phrases like "as your companion", "as your assistant", \
or "I'm here to". Just respond naturally.

- Reflect, explore ideas, and help the user think through problems.
- Be honest when you don't know something or when a question requires current data you lack.
- Match the user's energy: casual for casual topics, substantive when they need depth.\
"""

_EVENT_KEYWORDS: dict[str, list[str]] = {
    "sent": ["sent", "emailed", "messaged", "reached out to", "contacted"],
    "replied": ["replied", "responded", "got back", "wrote back"],
    "no_reply": ["no reply", "no response", "hasn't replied", "hasn't responded"],
    "bounced": ["bounced", "returned", "undeliverable"],
}

_CHANNEL_KEYWORDS: dict[str, list[str]] = {
    "email": ["email", "emailed"],
    "linkedin": ["linkedin"],
    "sms": ["sms", "text", "texted", "whatsapp"],
    "phone": ["call", "called", "phone", "rang"],
}


@register
class CompanionAgent(BaseAgent):
    name  = "companion"
    tools = ["extract_facts", "extract_contacts", "log_outreach_event"]

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        settings: Settings,
        person_store: PersonStore,
        pool: asyncpg.Pool,
    ) -> None:
        super().__init__(settings)
        self._client = openrouter_client
        self._person_store = person_store
        self._pool = pool

    async def run(self, ctx: AgentContext) -> AgentResult:
        await self.emit(ctx, "companion.thinking")
        response = await self._client.complete(
            messages=ctx.messages,
            model=self._model(ctx),
            system=self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx),
        )

        facts_tc, contacts_tc, outreach_tc = await asyncio.gather(
            self.call_tool(
                "extract_facts", ctx,
                prompt=ctx.prompt,
                response=response,
                client=self._client,
                model=self._model(ctx),
            ),
            self.call_tool(
                "extract_contacts", ctx,
                prompt=ctx.prompt,
                response=response,
                client=self._client,
                model=self._model(ctx),
            ),
            self._attempt_log_outreach(ctx),
        )

        proposals = to_user_facts(facts_tc.result or [])
        contact_proposals = contacts_tc.result or []

        self._log.info(
            "companion_agent_complete",
            session_id=ctx.session_id,
            proposals=len(proposals),
            contact_proposals=len(contact_proposals),
        )

        return AgentResult(
            agent=self.name,
            response=response,
            tool_calls=[facts_tc, contacts_tc, outreach_tc],
            memory_proposals=proposals,
            contact_proposals=contact_proposals,
        )

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        async for token in self._client.stream(
            messages=ctx.messages,
            model=self._model(ctx),
            system=self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx),
        ):
            yield token

    async def _attempt_log_outreach(self, ctx: AgentContext) -> ToolCall:
        event = _detect_outreach_event(ctx.prompt)
        if event is None:
            return ToolCall(
                tool_name="log_outreach_event",
                args={},
                result=None,
                duration_ms=0,
                success=False,
                error="no outreach event detected",
            )
        return await self.call_tool(
            "log_outreach_event", ctx,
            contact_name=event["contact_name"],
            event_type=event["event_type"],
            channel=event["channel"],
            notes=ctx.prompt,
            pool=self._pool,
            person_store=self._person_store,
        )


def _detect_outreach_event(text: str) -> dict | None:
    lower = text.lower()

    event_type = None
    for et, keywords in _EVENT_KEYWORDS.items():
        if any(k in lower for k in keywords):
            event_type = et
            break

    if event_type is None:
        return None

    # Extract first proper noun (likely the contact name)
    names = re.findall(r"\b[A-Z][a-záàâãéèêíïóôõöúüçñ]+(?:\s+[A-Z][a-záàâãéèêíïóôõöúüçñ]+)?\b", text)
    if not names:
        return None

    channel = "other"
    for ch, keywords in _CHANNEL_KEYWORDS.items():
        if any(k in lower for k in keywords):
            channel = ch
            break

    return {"contact_name": names[0], "event_type": event_type, "channel": channel}
