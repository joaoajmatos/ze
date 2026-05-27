import pytest
from unittest.mock import AsyncMock

from ze.agents.research.agent import ResearchAgent
from ze.agents.research.tools import format_search_results
from ze.agents.types import AgentContext, AgentResult, ToolCall
from ze.logging import configure_logging
from ze.memory.types import MemoryContext, UserFact


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_settings():
    import pathlib
    from ze.settings import Settings, get_settings
    get_settings.cache_clear()
    real_config = pathlib.Path(__file__).parent.parent.parent.parent / "config"
    return Settings(
        openrouter_api_key="test-key",
        database_url="postgresql://ze:ze@localhost:5432/ze",
        database_url_sync="postgresql+psycopg2://ze:ze@localhost:5432/ze",
        config_dir=real_config,
    )


def make_search_result(content: str = "Latest AI developments.") -> dict:
    return {"results": [{"title": "AI News", "url": "https://example.com", "content": content}]}


def make_client(
    loop_response: str = "Here is what I found.",
    facts_response: str = "[]",
) -> AsyncMock:
    """Return a mock OpenRouterClient.

    complete_with_tools returns text immediately (no tool-call round-trips).
    complete is used by extract_facts internally.
    """
    client = AsyncMock()
    client.complete_with_tools = AsyncMock(return_value=(loop_response, None))
    client.complete = AsyncMock(return_value=facts_response)

    async def _stream(*args, **kwargs):
        for token in loop_response.split():
            yield token

    client.stream = _stream
    return client


def make_tavily(content: str = "Latest AI developments.") -> AsyncMock:
    tavily = AsyncMock()
    tavily.search = AsyncMock(return_value=make_search_result(content))
    return tavily


def make_ctx(prompt: str = "find AI news", memory: MemoryContext | None = None) -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt=prompt,
        intent="read",
        memory=memory or MemoryContext(),
        messages=[{"role": "user", "content": prompt}],
    )


def make_agent(client=None, tavily=None) -> ResearchAgent:
    settings = make_settings()
    return ResearchAgent(
        openrouter_client=client or make_client(),
        tavily_client=tavily or make_tavily(),
        settings=settings,
    )


@pytest.fixture(autouse=True)
def setup_logging():
    configure_logging()


# ── Registry ──────────────────────────────────────────────────────────────────

def test_research_agent_is_registered():
    from ze.agents.registry import _registry
    assert "research" in _registry


# ── run() — basic structure ───────────────────────────────────────────────────

async def test_run_returns_agent_result():
    agent = make_agent()
    result = await agent.run(make_ctx())
    assert isinstance(result, AgentResult)
    assert result.agent == "research"


async def test_run_returns_response_from_agentic_loop():
    client = make_client(loop_response="Here is the latest AI news.")
    agent = make_agent(client=client)
    result = await agent.run(make_ctx("find AI news"))
    assert result.response == "Here is the latest AI news."


async def test_run_always_includes_extract_facts_call():
    agent = make_agent()
    result = await agent.run(make_ctx())
    tool_names = [tc.tool_name for tc in result.tool_calls]
    assert "extract_facts" in tool_names


async def test_run_extract_facts_is_last_tool_call():
    agent = make_agent()
    result = await agent.run(make_ctx())
    assert result.tool_calls[-1].tool_name == "extract_facts"


# ── run() — agentic loop with tool-call round-trips ──────────────────────────

async def test_run_single_search_iteration():
    """LLM requests one web_search then returns text."""
    client = AsyncMock()
    client.complete_with_tools = AsyncMock(side_effect=[
        (None, [{"id": "c1", "name": "web_search", "arguments": {"query": "AI news"}}]),
        ("Here is what I found.", None),
    ])
    client.complete = AsyncMock(return_value="[]")  # extract_facts
    tavily = make_tavily()
    agent = make_agent(client=client, tavily=tavily)

    result = await agent.run(make_ctx("AI news"))

    assert result.response == "Here is what I found."
    web_calls = [tc for tc in result.tool_calls if tc.tool_name == "web_search"]
    assert len(web_calls) == 1
    tavily.search.assert_awaited_once_with("AI news", max_results=5)


async def test_run_multiple_search_iterations():
    """LLM requests two searches before producing text."""
    client = AsyncMock()
    client.complete_with_tools = AsyncMock(side_effect=[
        (None, [{"id": "c1", "name": "web_search", "arguments": {"query": "AI 2024"}}]),
        (None, [{"id": "c2", "name": "web_search", "arguments": {"query": "AI 2025"}}]),
        ("Comprehensive answer.", None),
    ])
    client.complete = AsyncMock(return_value="[]")
    tavily = make_tavily()
    agent = make_agent(client=client, tavily=tavily)

    result = await agent.run(make_ctx("AI trends"))

    assert result.response == "Comprehensive answer."
    web_calls = [tc for tc in result.tool_calls if tc.tool_name == "web_search"]
    assert len(web_calls) == 2
    assert tavily.search.await_count == 2


async def test_run_no_search_when_llm_answers_directly():
    """LLM returns text on first call — no web_search is made."""
    tavily = make_tavily()
    agent = make_agent(tavily=tavily)  # make_client returns text immediately
    result = await agent.run(make_ctx())
    assert tavily.search.await_count == 0
    web_calls = [tc for tc in result.tool_calls if tc.tool_name == "web_search"]
    assert len(web_calls) == 0


async def test_run_handles_search_failure_gracefully():
    """Failed web_search result is still passed back to LLM; agent returns response."""
    tavily = AsyncMock()
    tavily.search = AsyncMock(side_effect=Exception("Tavily down"))

    client = AsyncMock()
    client.complete_with_tools = AsyncMock(side_effect=[
        (None, [{"id": "c1", "name": "web_search", "arguments": {"query": "test"}}]),
        ("I could not find anything.", None),
    ])
    client.complete = AsyncMock(return_value="[]")
    agent = make_agent(client=client, tavily=tavily)

    result = await agent.run(make_ctx())

    assert result.response == "I could not find anything."
    assert result.tool_calls[0].success is False


async def test_run_with_memory_facts_injects_into_system_prompt():
    memory = MemoryContext(facts=[UserFact(key="name", value="Alice")])
    captured: list[str] = []

    client = AsyncMock()
    async def _complete_with_tools(messages, model, tools, system=None, **kwargs):
        if system:
            captured.append(system)
        return ("done", None)
    client.complete_with_tools = _complete_with_tools
    client.complete = AsyncMock(return_value="[]")

    agent = make_agent(client=client)
    await agent.run(make_ctx(memory=memory))

    assert captured
    assert "name: Alice" in captured[0]


# ── stream() ─────────────────────────────────────────────────────────────────

async def test_stream_yields_tokens():
    client = make_client(loop_response="hello world")
    agent = make_agent(client=client)
    tokens = [t async for t in agent.stream(make_ctx())]
    assert len(tokens) > 0
    assert "".join(tokens).strip() != ""


# ── format_search_results (used by stream()) ──────────────────────────────────

def test_format_search_results_success():
    tc = ToolCall(
        tool_name="web_search",
        args={},
        result={"results": [{"title": "T", "url": "https://u.co", "content": "body"}]},
        duration_ms=10,
        success=True,
    )
    text = format_search_results(tc)
    assert "body" in text
    assert "https://u.co" in text


def test_format_search_results_failed_tool_call():
    tc = ToolCall(
        tool_name="web_search",
        args={},
        result=None,
        duration_ms=5,
        success=False,
        error="timeout",
    )
    text = format_search_results(tc)
    assert "search failed" in text


def test_format_search_results_empty_results():
    tc = ToolCall(
        tool_name="web_search",
        args={},
        result={"results": []},
        duration_ms=5,
        success=True,
    )
    text = format_search_results(tc)
    assert "no search results" in text
