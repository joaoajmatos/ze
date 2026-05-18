import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze.agents.email.agent import EmailAgent
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
    )


def make_client(response: str = "Your inbox is empty.") -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=response)

    async def _stream(*args, **kwargs):
        for token in response.split():
            yield token

    client.stream = _stream
    return client


def make_credentials(messages: list | None = None) -> MagicMock:
    """Return a mock GoogleCredentials whose gmail service returns `messages`."""
    service = MagicMock()
    (
        service.users.return_value
             .messages.return_value
             .list.return_value
             .execute.return_value
    ) = {"messages": messages or []}

    creds = MagicMock()
    creds.gmail.return_value = service
    return creds


def make_ctx(prompt: str = "check my inbox") -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt=prompt,
        intent="read",
        memory=MemoryContext(),
    )


def make_agent(client=None, creds=None) -> EmailAgent:
    return EmailAgent(
        openrouter_client=client or make_client(),
        google_credentials=creds or make_credentials(),
        settings=make_settings(),
    )


@pytest.fixture(autouse=True)
def setup_logging():
    configure_logging()


# ── Registry ──────────────────────────────────────────────────────────────────

def test_email_agent_is_registered():
    from ze.agents.registry import _registry
    assert "email" in _registry


# ── run() ─────────────────────────────────────────────────────────────────────

async def test_run_returns_agent_result():
    result = await make_agent().run(make_ctx())
    assert isinstance(result, AgentResult)
    assert result.agent == "email"


async def test_run_includes_list_emails_and_extract_facts():
    result = await make_agent().run(make_ctx())
    names = [tc.tool_name for tc in result.tool_calls]
    assert "list_emails" in names
    assert "extract_facts" in names


async def test_run_augments_prompt_with_emails():
    msgs = [{"id": "msg1"}, {"id": "msg2"}]
    creds = make_credentials(messages=msgs)
    captured: list[str] = []

    client = AsyncMock()
    async def _complete(messages, **kwargs):
        captured.append(messages[0]["content"])
        return "You have 2 emails."
    client.complete = _complete

    await make_agent(client=client, creds=creds).run(make_ctx())
    assert captured and "msg1" in captured[0]


async def test_run_no_emails_does_not_augment():
    captured: list[str] = []

    client = AsyncMock()
    async def _complete(messages, **kwargs):
        captured.append(messages[0]["content"])
        return "Nothing."
    client.complete = _complete

    prompt = "check my inbox"
    await make_agent(client=client, creds=make_credentials(messages=[])).run(make_ctx(prompt))
    assert captured[0] == prompt


async def test_run_handles_gmail_failure_gracefully():
    service = MagicMock()
    (
        service.users.return_value
             .messages.return_value
             .list.return_value
             .execute.side_effect
    ) = Exception("Gmail API error")
    creds = MagicMock()
    creds.gmail.return_value = service

    result = await make_agent(creds=creds).run(make_ctx())
    inbox_tc = next(tc for tc in result.tool_calls if tc.tool_name == "list_emails")
    assert inbox_tc.success is False
    assert result.response  # LLM still runs


async def test_run_tool_call_has_duration():
    result = await make_agent().run(make_ctx())
    assert all(tc.duration_ms >= 0 for tc in result.tool_calls)


# ── stream() ─────────────────────────────────────────────────────────────────

async def test_stream_yields_tokens():
    client = make_client("You have three unread messages.")
    tokens = [t async for t in make_agent(client=client).stream(make_ctx())]
    assert len(tokens) > 0
    assert "".join(tokens).strip() != ""
