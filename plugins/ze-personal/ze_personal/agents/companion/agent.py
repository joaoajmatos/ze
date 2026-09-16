import re
from typing import AsyncIterator

import asyncpg

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent
from ze_agents.types import AgentContext, AgentResult, ToolCall
from ze_personal.contacts.store import PersonStore
from ze_agents.client import LLMClient
from ze_agents.settings import Settings
from ze_agents.types import Intent, Mode
from ze_personal.agents.companion.honesty import hold_token_sink, publish_honest_reply
from ze_sdk.memory import PostgresMemoryStore

_AGENT_INSTRUCTIONS = """\
You reason from what you know and what the user tells you — you do not search the web.
Never label your role or use phrases like "as your companion", "as your assistant", \
or "I'm here to". Just respond naturally.

- Reflect, explore ideas, and help the user think through problems.
- Be honest when you don't know something or when a question requires current data you lack.
- Match the user's energy: casual for casual topics, substantive when they need depth.

Memory tools:
- remember_fact: durable identity, preference, relationship, constraint, or contact \
detail the user asked you to remember (no fire time). Call it before claiming you will remember. \
Confirm only if the tool returns ok true.
- forget_fact: biography only ("forget that I like aisle seats"). Confirm only if ok is true. \
Never forget_fact for "forget the dentist" cancel speech, and never dual-write forget_fact \
after a reminder/loop/goal cancel on the same utterance.
If a memory tool returns ok false, say you could not store or retract it — never pretend you did.

Routing (time beats biography):
- Forget/cancel/drop/abandon a timed ping, lingering concern, or multi-week goal \
("forget the dentist"): delegate_to_agent agent_name=reminders, loops, or goals. \
Do not call forget_fact for that speech act. Two named targets are two delegate calls, \
never one batch retract.
- Timed ping / "remind me at …" / "remember to … on Tuesday": delegate_to_agent \
agent_name=reminders. Do not remember_fact that task.
- Lingering concern with no time and no multi-week plan: delegate_to_agent agent_name=loops.
- Multi-week outcome with a deadline: delegate_to_agent agent_name=goals.
- Named workflow only if the user clearly names that workflow.
- Ingest a file/PDF: not remember_fact. Acknowledge ingest or extraction. \
Do not confirm the file as a whole was remembered even if remember_fact also \
succeeded for a separate preference this turn.
- Ambiguous "keep this in mind" with no durable predicate: ask one clarifying question \
or treat as a loop — do not silently write a fact.
- Standing constraint ("never email after 22:00") is a fact. Gated mail, calendar, \
and reminder writes are checked against reviewed constraints. You may say you will \
not send or schedule because of a constraint only after that veto actually ran.\


Using what you already know:
- Apply retrieved facts silently when they change the answer (tone, constraints, names).
- Do not announce "I remember that you…" or dump the biography unsolicited.
- If the user asks what you know about them, answer from the biography block.\
"""

_EVENT_KEYWORDS: dict[str, list[str]] = {
    "no_reply": ["no reply", "no response", "hasn't replied", "hasn't responded"],
    "bounced": ["bounced", "returned", "undeliverable"],
    "replied": ["replied", "responded", "got back", "wrote back"],
    "sent": ["sent", "emailed", "messaged", "reached out to", "contacted"],
}

_CHANNEL_KEYWORDS: dict[str, list[str]] = {
    "email": ["email", "emailed"],
    "linkedin": ["linkedin"],
    "sms": ["sms", "text", "texted", "whatsapp"],
    "phone": ["call", "called", "phone", "rang"],
}


@agent
class CompanionAgent(BaseAgent):
    name = "companion"
    display_name = "Conversation & reasoning"
    description = """
      Chat, conversation, and reasoning that needs no external tools or live data.
      Use for: greetings ("hey", "how are you doing"), emotional check-ins ("I'm feeling
      stressed"), brainstorming, writing help, "explain X to me", "help me think through X",
      "what can you do", "what do you know about me", "tell me something interesting",
      and open-ended questions with no specific domain. Not for web search, calendar,
      email, reminders, news, or any query that needs fetching live data — delegate those.
      Timed "remember to / remind me" is a reminder, not a biography fact. Multi-week
      outcomes go to the goal agent. Lingering concerns without a fire time are open loops.
    """
    model = "anthropic/claude-sonnet-4-5"
    model_simple = "anthropic/claude-haiku-4-5"
    vision_capable = True
    timeout = 60
    tools = ["remember_fact", "forget_fact", "delegate_to_agent"]
    intents = {
        "reason": Intent(
            Mode.AUTONOMOUS, "Reason, converse, and answer questions directly."
        ),
    }
    default_mode = Mode.AUTONOMOUS

    def __init__(
        self,
        openrouter_client: LLMClient,
        settings: Settings,
        person_store: PersonStore,
        pool: asyncpg.Pool,
        memory_store: PostgresMemoryStore,
    ) -> None:
        self._settings = settings
        self._client = openrouter_client
        self._person_store = person_store
        self._pool = pool
        self._memory_store = memory_store

    async def run(self, ctx: AgentContext) -> AgentResult:
        await self.emit(ctx, "companion.thinking")
        original_sink = hold_token_sink(ctx)
        try:
            response, loop_tool_calls = await self.agentic_loop(
                ctx,
                client=self._client,
                messages=list(ctx.messages),
                system=self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx),
                deps={"memory_store": self._memory_store},
            )
        finally:
            ctx.token_sink = original_sink

        tool_calls = list(loop_tool_calls)
        outreach_tc = await self._attempt_log_outreach(ctx)
        if outreach_tc is not None and outreach_tc.success:
            tool_calls.append(outreach_tc)

        gated = await publish_honest_reply(
            original_sink, response, tool_calls, user_text=ctx.prompt
        )

        self._log.info("companion_agent_complete", session_id=ctx.session_id)
        return AgentResult(agent=self.name, response=gated, tool_calls=tool_calls)

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        result = await self.run(ctx)
        yield result.response

    async def _attempt_log_outreach(self, ctx: AgentContext) -> ToolCall | None:
        event = _detect_outreach_event(ctx.prompt)
        if event is None:
            return None
        return await self.call_tool(
            "log_outreach_event",
            ctx,
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

    names = re.findall(
        r"\b[A-Z][a-záàâãéèêíïóôõöúüçñ]+(?:\s+[A-Z][a-záàâãéèêíïóôõöúüçñ]+)?\b",
        text,
    )
    if not names:
        return None

    channel = "other"
    for ch, keywords in _CHANNEL_KEYWORDS.items():
        if any(k in lower for k in keywords):
            channel = ch
            break

    return {"contact_name": names[0], "event_type": event_type, "channel": channel}
