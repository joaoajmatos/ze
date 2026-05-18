import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze.agents.calendar.agent import CalendarAgent
from ze.agents.types import AgentContext, AgentResult
from ze.logging import configure_logging
from ze.memory.types import MemoryContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_settings():
    from ze.settings import Settings, get_settings
    get_settings.cache_clear()
    real_config = pathlib.Path(__file__).parent.parent.parent.parent / "config"
    return Settings(
        openrouter_api_key="test-key",
        database_url="postgresql://ze:ze@localhost:5432/ze",
        database_url_sync="postgresql+psycopg2://ze:ze@localhost:5432/ze",
        config_dir=real_config,
        timezone="Europe/Lisbon",
    )


def make_client(response: str = "You have no upcoming events.") -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=response)

    async def _stream(*args, **kwargs):
        for token in response.split():
            yield token

    client.stream = _stream
    return client


def make_credentials(events: list | None = None) -> MagicMock:
    """Return a mock GoogleCredentials whose calendar service returns `events`."""
    service = MagicMock()
    (
        service.events.return_value
             .list.return_value
             .execute.return_value
    ) = {"items": events or []}

    creds = MagicMock()
    creds.calendar.return_value = service
    return creds


def make_ctx(prompt: str = "what do I have today?") -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt=prompt,
        intent="read",
        memory=MemoryContext(),
    )


def make_agent(client=None, creds=None) -> CalendarAgent:
    return CalendarAgent(
        openrouter_client=client or make_client(),
        google_credentials=creds or make_credentials(),
        settings=make_settings(),
    )


@pytest.fixture(autouse=True)
def setup_logging():
    configure_logging()


# ── Registry ──────────────────────────────────────────────────────────────────

def test_calendar_agent_is_registered():
    from ze.agents.registry import _registry
    assert "calendar" in _registry


# ── run() ─────────────────────────────────────────────────────────────────────

async def test_run_returns_agent_result():
    result = await make_agent().run(make_ctx())
    assert isinstance(result, AgentResult)
    assert result.agent == "calendar"


async def test_run_includes_list_events_and_extract_facts():
    result = await make_agent().run(make_ctx())
    names = [tc.tool_name for tc in result.tool_calls]
    assert "list_events" in names
    assert "extract_facts" in names


async def test_run_augments_prompt_with_events():
    events = [{"summary": "Dentist", "start": {"dateTime": "2026-05-20T10:00:00"}}]
    creds = make_credentials(events=events)
    captured: list[str] = []

    client = AsyncMock()
    async def _complete(messages, **kwargs):
        captured.append(messages[0]["content"])
        return "You have a dentist appointment."
    client.complete = _complete

    await make_agent(client=client, creds=creds).run(make_ctx())
    assert captured and "Dentist" in captured[0]


async def test_run_no_events_does_not_augment():
    captured: list[str] = []

    client = AsyncMock()
    async def _complete(messages, **kwargs):
        captured.append(messages[0]["content"])
        return "Nothing today."
    client.complete = _complete

    await make_agent(client=client, creds=make_credentials(events=[])).run(make_ctx("what today?"))
    assert captured[0] == "what today?"


async def test_run_injects_timezone_into_system_prompt():
    captured_system: list[str] = []

    client = AsyncMock()
    async def _complete(messages, system=None, **kwargs):
        if system:
            captured_system.append(system)
        return "ok"
    client.complete = _complete

    await make_agent(client=client).run(make_ctx())
    assert captured_system
    assert "Europe/Lisbon" in captured_system[0]


async def test_run_handles_calendar_failure_gracefully():
    service = MagicMock()
    service.events.return_value.list.return_value.execute.side_effect = Exception("API error")
    creds = MagicMock()
    creds.calendar.return_value = service

    result = await make_agent(creds=creds).run(make_ctx())
    events_tc = next(tc for tc in result.tool_calls if tc.tool_name == "list_events")
    assert events_tc.success is False
    assert result.response  # LLM still runs


async def test_run_tool_call_has_duration():
    result = await make_agent().run(make_ctx())
    assert all(tc.duration_ms >= 0 for tc in result.tool_calls)


# ── stream() ─────────────────────────────────────────────────────────────────

async def test_stream_yields_tokens():
    client = make_client("Monday Tuesday Wednesday")
    tokens = [t async for t in make_agent(client=client).stream(make_ctx())]
    assert len(tokens) > 0
    assert "".join(tokens).strip() != ""
