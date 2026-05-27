"""Tests for OpenRouterClient — all HTTP is mocked via aiohttp mock."""
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ze_core.openrouter.client import OpenRouterClient, _build_messages


# ── _build_messages ───────────────────────────────────────────────────────────

class TestBuildMessages:
    def test_no_system_returns_messages_unchanged(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = _build_messages(msgs, None)
        assert result == msgs

    def test_system_prepended(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = _build_messages(msgs, "You are helpful.")
        assert result[0] == {"role": "system", "content": "You are helpful."}
        assert result[1] == msgs[0]

    def test_empty_system_not_prepended(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = _build_messages(msgs, "")
        assert result == msgs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_session(json_response: dict) -> MagicMock:
    """Build a mock aiohttp.ClientSession whose post() returns json_response."""
    resp = AsyncMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=json_response)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.post = MagicMock(return_value=cm)
    return session


def _text_response(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content, "tool_calls": None}}]
    }


def _tool_response(tool_calls: list[dict]) -> dict:
    return {
        "choices": [{"message": {"content": None, "tool_calls": tool_calls}}]
    }


def _client(session: MagicMock | None = None) -> OpenRouterClient:
    c = OpenRouterClient(api_key="test-key")
    if session is not None:
        c._session = session
    return c


# ── complete ──────────────────────────────────────────────────────────────────

class TestComplete:
    async def test_returns_message_content(self):
        session = _mock_session(_text_response("Hello!"))
        c = _client(session)
        result = await c.complete([{"role": "user", "content": "hi"}], model="m")
        assert result == "Hello!"

    async def test_system_param_prepended(self):
        session = _mock_session(_text_response("ok"))
        c = _client(session)
        await c.complete(
            [{"role": "user", "content": "hi"}],
            model="m",
            system="You are helpful.",
        )
        payload = session.post.call_args[1]["json"]
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "You are helpful."

    async def test_temperature_included_in_payload(self):
        session = _mock_session(_text_response("ok"))
        c = _client(session)
        await c.complete(
            [{"role": "user", "content": "hi"}],
            model="m",
            temperature=0.9,
        )
        payload = session.post.call_args[1]["json"]
        assert payload["temperature"] == pytest.approx(0.9)

    async def test_response_format_included_when_set(self):
        session = _mock_session(_text_response("{}"))
        c = _client(session)
        await c.complete(
            [{"role": "user", "content": "hi"}],
            model="m",
            response_format={"type": "json_object"},
        )
        payload = session.post.call_args[1]["json"]
        assert payload["response_format"] == {"type": "json_object"}

    async def test_response_format_absent_when_none(self):
        session = _mock_session(_text_response("ok"))
        c = _client(session)
        await c.complete([{"role": "user", "content": "hi"}], model="m")
        payload = session.post.call_args[1]["json"]
        assert "response_format" not in payload

    async def test_max_tokens_included_when_set(self):
        session = _mock_session(_text_response("ok"))
        c = _client(session)
        await c.complete([{"role": "user", "content": "hi"}], model="m", max_tokens=100)
        payload = session.post.call_args[1]["json"]
        assert payload["max_tokens"] == 100

    async def test_kwargs_forwarded_to_payload(self):
        session = _mock_session(_text_response("ok"))
        c = _client(session)
        await c.complete(
            [{"role": "user", "content": "hi"}],
            model="m",
            seed=42,
        )
        payload = session.post.call_args[1]["json"]
        assert payload["seed"] == 42


# ── complete_with_tools ───────────────────────────────────────────────────────

class TestCompleteWithTools:
    def _tc_response(self, name: str, args: dict, call_id: str = "c1") -> dict:
        return _tool_response([{
            "id": call_id,
            "function": {
                "name": name,
                "arguments": json.dumps(args),
            },
        }])

    async def test_text_response_returns_text_none(self):
        session = _mock_session(_text_response("final answer"))
        c = _client(session)
        text, calls = await c.complete_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            model="m",
            tools=[],
        )
        assert text == "final answer"
        assert calls is None

    async def test_tool_call_response_returns_none_calls(self):
        session = _mock_session(self._tc_response("search", {"q": "python"}))
        c = _client(session)
        text, calls = await c.complete_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            model="m",
            tools=[],
        )
        assert text is None
        assert calls is not None
        assert len(calls) == 1
        assert calls[0]["name"] == "search"
        assert calls[0]["arguments"] == {"q": "python"}
        assert calls[0]["id"] == "c1"

    async def test_tool_schemas_wrapped_as_functions(self):
        session = _mock_session(_text_response("ok"))
        c = _client(session)
        tool_schema = {"name": "my_tool", "description": "does stuff", "parameters": {}}
        await c.complete_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            model="m",
            tools=[tool_schema],
        )
        payload = session.post.call_args[1]["json"]
        assert payload["tools"] == [{"type": "function", "function": tool_schema}]

    async def test_system_prepended(self):
        session = _mock_session(_text_response("ok"))
        c = _client(session)
        await c.complete_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            model="m",
            tools=[],
            system="You are helpful.",
        )
        payload = session.post.call_args[1]["json"]
        assert payload["messages"][0]["role"] == "system"

    async def test_invalid_json_args_gives_empty_dict(self):
        bad_json_response = _tool_response([{
            "id": "c1",
            "function": {"name": "t", "arguments": "not-json"},
        }])
        session = _mock_session(bad_json_response)
        c = _client(session)
        _, calls = await c.complete_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            model="m",
            tools=[],
        )
        assert calls[0]["arguments"] == {}

    async def test_multiple_tool_calls_returned(self):
        response = _tool_response([
            {"id": "c1", "function": {"name": "t1", "arguments": "{}"}},
            {"id": "c2", "function": {"name": "t2", "arguments": '{"x": 1}'}},
        ])
        session = _mock_session(response)
        c = _client(session)
        _, calls = await c.complete_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            model="m",
            tools=[],
        )
        assert len(calls) == 2
        assert calls[0]["name"] == "t1"
        assert calls[1]["arguments"] == {"x": 1}


# ── aclose ────────────────────────────────────────────────────────────────────

class TestAclose:
    async def test_closes_session(self):
        session = MagicMock()
        session.close = AsyncMock()
        c = _client(session)
        await c.aclose()
        session.close.assert_awaited_once()
        assert c._session is None

    async def test_aclose_idempotent(self):
        c = _client()
        await c.aclose()  # session is None — should not raise
