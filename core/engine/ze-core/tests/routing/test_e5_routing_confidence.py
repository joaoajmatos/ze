from unittest.mock import AsyncMock

import pytest

from ze_agents.registry import agent, clear_registry
from ze_agents.types import AgentContext, AgentResult, Intent, Mode
from ze_core.embeddings import get_embedder
from ze_core.routing.router import EmbeddingRouter
from ze_core.routing.types import RouterConfig


def _register(name: str, description: str) -> None:
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=name, response="")

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = description
    _A.enabled = True
    _A.model = "m"
    _A.model_simple = None
    _A.intents = {"read": Intent(Mode.AUTONOMOUS, "Read")}
    agent(_A)


@pytest.mark.slow
async def test_live_e5_clear_calendar_english_skips_decompose():
    clear_registry()
    _register(
        "calendar",
        """Google Calendar events, meetings, and appointments.
      Use for: "what's on my calendar today", "what do I have tomorrow", "what's this week",
      "add a meeting with X on Friday at 3pm", "schedule a call", "create an event",
      "find a free time slot", "am I free on Thursday", "delete my dentist appointment",
      "update my 2pm meeting". Not for one-off personal reminders or email.""",
    )
    _register(
        "messenger",
        """Messaging and inbox management across communication channels.
      Use for: "do I have any emails from X", "check my inbox", "what's in my email",
      "draft a message to X about Y", "send an email to X", "reply to X's email",
      "forward this email", "summarise my email thread", "archive this email",
      "search my inbox for X". Not for calendar events or reminders.""",
    )
    client = AsyncMock()
    client.complete = AsyncMock()
    router = EmbeddingRouter(
        get_embedder(),
        client,
        routing_store=None,
        config=RouterConfig(),
    )
    env = await router.route("what's on my calendar tomorrow", "s1")
    assert env.primary_agent == "calendar"
    assert env.is_compound is False
    client.complete.assert_not_called()
    clear_registry()
