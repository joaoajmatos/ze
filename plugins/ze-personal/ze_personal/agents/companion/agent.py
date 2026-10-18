import re
from typing import AsyncIterator

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import agent
from ze_agents.types import AgentContext, AgentResult, ToolCall
from ze_priority import WorldComposer
from ze_personal.agents.companion.outreach_log import OutreachLog
from ze_personal.contacts.store import PersonStore
from ze_agents.client import LLMClient
from ze_agents.settings import Settings
from ze_sdk import hold_token_sink, publish_honest_reply
from ze_sdk.memory import PostgresMemoryStore
from ze_sdk.proactive import NotificationStore

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
- delegate_to_agent requires agent_name and objective. Optional fat fields: \
prior_outputs, inputs, output_shape, stop_condition. Do not pass task or context.
- Forget/cancel/drop/abandon a timed ping, lingering concern, or multi-week goal \
("forget the dentist"): delegate_to_agent agent_name=reminders, loops, or goals \
with an objective. Do not call forget_fact for that speech act. Two named targets \
are two delegate calls, never one batch retract.
- Timed ping / "remind me at …" / "remember to … on Tuesday": delegate_to_agent \
agent_name=reminders with an objective. Do not remember_fact that task.
- Lingering concern with no time and no multi-week plan: delegate_to_agent \
agent_name=loops with an objective.
- Multi-week outcome with a deadline: delegate_to_agent agent_name=goals \
with an objective.
- Named workflow only if the user clearly names that workflow.
- Ingest a file/PDF: not remember_fact. Acknowledge ingest or extraction. \
Do not confirm the file as a whole was remembered even if remember_fact also \
succeeded for a separate preference this turn.
- Ambiguous "keep this in mind" with no durable predicate: ask one clarifying question \
or treat as a loop — do not silently write a fact.
- Standing constraint ("never email after 22:00") is a fact. Gated mail, calendar, \
and reminder writes are checked against reviewed constraints. You may say you will \
not send or schedule because of a constraint only after that veto actually ran.

Conductor:
- You own the user-facing reply. Specialists never speak to the user.
- Haiku routing hints are optional suggestions, not a plan you must execute as a DAG.
- Scale effort: one delegate for a simple single-domain ask (e.g. Tuesday's calendar). \
Do not invent four specialists for a one-agent question.
- Sequential mixed work: brief each specialist with delegate_to_agent using fat fields, \
judge done / next / ask the user. Pass prior_outputs into the next brief.
- One silent retry of the same specialist after a stall (empty or error). If it stalls \
again, or that name was already called twice, or six delegates ran this turn, ask the \
user. Do not keep replanning.
- If this conductor job cannot finish this turn (specialist ledger not all done) \
and you are not already asking a stall question, offer to continue it as a goal \
(multi-week outcome) or a workflow (repeatable or scheduled unattended work). \
Do not create either until the user accepts or says to keep going on this.
- Do not auto-offer promote when every ledger step is done.
- Keep going / accept: delegate_to_agent to goals (create_goal) or workflow \
(create_workflow) with the conductor ledger and prior_outputs in the brief. \
Never both. If ambiguous, ask once which. Capability confirmation still applies. \
Never write procedures or memory_procedures.

Showing results:
- Prose is the default. Call a render_* tool only when structure helps more than a \
sentence would, then add one line of context.
- render_chart for a trend or comparison over time or categories (line, bar, area, \
pie) when you hold the numbers; render_table for rows with several columns; \
render_metric for one headline figure; render_timeline for dated events in order; \
render_connections for patterns you found across the user's history.
- render_form, render_choice_group, render_consent, render_connect_account and \
render_review only while the user is setting something up or choosing between \
options. Never for casual chat or emotional check-ins.
- When the user asks what access you would need before connecting an account, call \
render_consent with one scope per permission (id, label, description), then \
render_connect_account for the account. Both calls, every time; never describe the \
scopes in prose instead of render_consent.
- Never render numbers you do not have. Delegate to get the data first, or say you \
lack it.
- Never narrate the tool call ("I'll render a chart") and never repeat the \
rendered content in prose.

Composed answers:
- What's slipping, late or drifting: call show_slipping.
- What needs me, what should I decide: call show_decisions.
- How is <project or topic> going: call show_topic with the user's own words.
- The modules appear on screen. Write one or two sentences from the returned summary only; \
never list every card and never add items it does not contain. If sources_failed is not \
empty, say which part you could not read.
- When a "Composed answer" note is already in this turn, the modules are on screen \
already: do not call the tool again, just write the sentence.

Briefings:
- Any question about a briefing Ze already sent ("how did the morning briefing do", \
"what was in it", "did you send it today"): call get_briefing and answer from it \
only: when it was sent, delivered or held, whether it was marked read in the notification centre \
(never say the user opened or read it), and what it covered. If delivery_status is \
"not confirmed as delivered", say that. If found is false, say no briefing is on record. For a briefing question \
never fetch news or delegate to news.

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
      Chat, conversation, reasoning, and coordinating specialists in one reply.
      Use for: greetings, emotional check-ins, brainstorming, writing help,
      "help me think through X", "what can you do", biography
      questions, and work that needs more than one specialist in sequence
      (calendar then email, research then a message). You speak; specialists do not.
      Scale effort: one specialist for a single-domain ask — not a four-step plan
      for "what's on Tuesday". Not for web search, calendar, email, reminders, or
      news as your own tools — delegate those. Timed "remember to / remind me" is
      a reminder. Multi-week outcomes go to goals. Lingering concerns without a
      fire time are open loops.
    """
    routing_criteria = """
      Use for: chat and greetings, emotional check-ins, reasoning about the user's own
      situation or decisions, writing help, questions about a briefing Ze already
      sent (when, what it covered, whether it was marked read), questions about what you know of the user,
      and requests that need several specialists in turn.
      Not for: a matter the user is undecided about and asks you to keep on their radar
      or keep an eye on (open loops), anything that needs facts from the web, a
      comparison, a how-to, or recent events. Those go to the agent that searches the web, even when you could
      answer from memory. Not for calendar, email, reminders or news either.
      A question about a briefing Ze already sent, even worded "did you send it",
      is yours, not email.
    """
    model = "anthropic/claude-sonnet-4-5"
    model_simple = "anthropic/claude-haiku-4-5"
    timeout = 60
    tools = [
        "remember_fact",
        "forget_fact",
        "delegate_to_agent",
        "render_table",
        "render_chart",
        "render_metric",
        "render_timeline",
        "render_form",
        "render_choice_group",
        "render_consent",
        "render_connect_account",
        "render_review",
        "render_connections",
        "show_slipping",
        "show_decisions",
        "show_topic",
        "get_briefing",
    ]

    def __init__(
        self,
        openrouter_client: LLMClient,
        settings: Settings,
        person_store: PersonStore,
        memory_store: PostgresMemoryStore,
        outreach_log: OutreachLog | None = None,
        world_composer: WorldComposer | None = None,
        notification_store: NotificationStore | None = None,
    ) -> None:
        self._settings = settings
        self._client = openrouter_client
        self._person_store = person_store
        self._outreach_log = outreach_log
        self._memory_store = memory_store
        self._world_composer = world_composer
        self._notification_store = notification_store

    def tool_deps(self) -> dict:
        return {
            "memory_store": self._memory_store,
            "notification_store": self._notification_store,
        }

    async def run(self, ctx: AgentContext) -> AgentResult:
        await self.emit(ctx, "companion.thinking")
        original_sink = hold_token_sink(ctx)
        try:
            response, loop_tool_calls = await self.agentic_loop(
                ctx,
                client=self._client,
                messages=list(ctx.messages),
                system=self._build_system_prompt(_AGENT_INSTRUCTIONS, ctx),
                deps={
                    **self.tool_deps(),
                    "world_composer": self._world_composer,
                    "preset": ctx.preset,
                    "notification_store": self._notification_store,
                },
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
        if self._outreach_log is None:
            return None
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
            campaign_store=self._outreach_log,
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
