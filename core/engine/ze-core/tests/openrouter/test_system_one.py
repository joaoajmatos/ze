"""OpenRouterSystemOneClient — HTTP mocked; never hits OpenRouter."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from ze_agents.system_one import SystemOneQuestion
from ze_core.openrouter.system_one import (
    DisabledSystemOneClient,
    OpenRouterSystemOneClient,
    build_system_one_client,
)

_QUESTIONS = {
    "is_bug": SystemOneQuestion(type="noul", instructions="Is this a bug?"),
    "team": SystemOneQuestion(
        type="choice",
        instructions="Which team?",
        criteria={"account": "login", "payments": "billing"},
    ),
    "urgency": SystemOneQuestion(
        type="score",
        instructions="How urgent?",
        criteria=["Can wait", "This week", "Blocking"],
    ),
}

_OK_PAYLOAD = {
    "id": "gen-dec-test",
    "model": "typesafe/jev-1.13-20260917",
    "provider": "TypeSafe",
    "answers": {
        "is_bug": {"type": "noul", "noul": 0.96},
        "team": {
            "type": "choice",
            "choice": "payments",
            "confidence": 0.75,
            "probabilities": {"account": 0.0, "payments": 0.84, "frontend": 0.16},
        },
        "urgency": {
            "type": "score",
            "score": 1.99,
            "confidence": 0.99,
            "probabilities": {"0": 0.0, "1": 0.01, "2": 0.99},
        },
    },
    "usage": {"input_tokens": 275, "output_tokens": 20, "cost": 0.00003},
}


def _client(**kwargs) -> OpenRouterSystemOneClient:
    defaults = {
        "api_key": "sk-or-test",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "typesafe/jev-1.13",
        "timeout_ms": 2000,
    }
    defaults.update(kwargs)
    return OpenRouterSystemOneClient(**defaults)


def _mock_http(response: MagicMock | AsyncMock):
    inst = AsyncMock()
    inst.__aenter__.return_value = inst
    inst.__aexit__.return_value = None
    inst.post = AsyncMock(return_value=response) if not isinstance(response, list) else AsyncMock(side_effect=response)
    return inst


def _json_response(status: int, payload: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload or {}
    return resp


@patch("ze_core.openrouter.system_one.httpx.AsyncClient")
async def test_ok_maps_noul_choice_score(mock_cls):
    inst = _mock_http(_json_response(200, _OK_PAYLOAD))
    mock_cls.return_value = inst
    tracker = MagicMock()
    result = await _client(cost_tracker=tracker).evaluate("blank checkout", _QUESTIONS)

    assert result.outcome == "ok"
    assert result.answers["is_bug"].noul == 0.96
    assert result.answers["team"].choice == "payments"
    assert result.answers["team"].probabilities["payments"] == 0.84
    assert result.answers["team"].confidence == 0.75
    assert result.answers["urgency"].score == 1.99
    assert result.model == "typesafe/jev-1.13-20260917"
    assert result.input_tokens == 275
    call_url = inst.post.await_args.args[0]
    assert call_url.endswith("/systemone")
    assert "/chat/completions" not in call_url
    body = inst.post.await_args.kwargs["json"]
    assert body["model"] == "typesafe/jev-1.13"
    tracker.record.assert_called_once()
    assert tracker.record.call_args.kwargs["model"] == "typesafe/jev-1.13-20260917"
    assert tracker.record.call_args.kwargs["generation_id"] == "gen-dec-test"


async def test_disabled_skips_without_http():
    with patch("ze_core.openrouter.system_one.httpx.AsyncClient") as mock_cls:
        result = await DisabledSystemOneClient().evaluate("x", _QUESTIONS)
    assert result.outcome == "skip"
    assert result.skip_reason == "disabled"
    mock_cls.assert_not_called()


async def test_missing_key_skips_without_http():
    with patch("ze_core.openrouter.system_one.httpx.AsyncClient") as mock_cls:
        result = await _client(api_key="").evaluate("x", _QUESTIONS)
    assert result.skip_reason == "missing_key"
    mock_cls.assert_not_called()


async def test_empty_questions_invalid_without_http():
    with patch("ze_core.openrouter.system_one.httpx.AsyncClient") as mock_cls:
        result = await _client().evaluate("x", {})
    assert result.skip_reason == "invalid_request"
    mock_cls.assert_not_called()


async def test_empty_state_invalid_without_http():
    with patch("ze_core.openrouter.system_one.httpx.AsyncClient") as mock_cls:
        result = await _client().evaluate({}, _QUESTIONS)
    assert result.skip_reason == "invalid_request"
    mock_cls.assert_not_called()


@patch("ze_core.openrouter.system_one.httpx.AsyncClient")
async def test_timeout_skips(mock_cls):
    inst = _mock_http(httpx.TimeoutException("timed out"))
    inst.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_cls.return_value = inst
    result = await _client().evaluate("x", _QUESTIONS)
    assert result.skip_reason == "timeout"


@patch("ze_core.openrouter.system_one.asyncio.sleep", new_callable=AsyncMock)
@patch("ze_core.openrouter.system_one.httpx.AsyncClient")
async def test_429_skips_overload(mock_cls, _sleep):
    inst = _mock_http([
        _json_response(429),
        _json_response(429),
        _json_response(429),
    ])
    mock_cls.return_value = inst
    result = await _client().evaluate("x", _QUESTIONS)
    assert result.skip_reason == "overload"


@patch("ze_core.openrouter.system_one.asyncio.sleep", new_callable=AsyncMock)
@patch("ze_core.openrouter.system_one.httpx.AsyncClient")
async def test_529_skips_overload(mock_cls, _sleep):
    inst = _mock_http([
        _json_response(529),
        _json_response(529),
        _json_response(529),
    ])
    mock_cls.return_value = inst
    result = await _client().evaluate("x", _QUESTIONS)
    assert result.skip_reason == "overload"


@patch("ze_core.openrouter.system_one.httpx.AsyncClient")
async def test_422_skips_error(mock_cls):
    inst = _mock_http(_json_response(422, {"error": "bad"}))
    mock_cls.return_value = inst
    result = await _client().evaluate("x", _QUESTIONS)
    assert result.skip_reason == "error"


def test_build_disabled_when_flag_off():
    settings = SimpleNamespace(
        openrouter_api_key="sk-or-test",
        openrouter_base_url="https://openrouter.ai/api/v1",
        config={"system_one": {"enabled": False, "model": "typesafe/jev-1.13"}},
    )
    client = build_system_one_client(settings)
    assert isinstance(client, DisabledSystemOneClient)


def test_build_live_when_enabled_even_without_key():
    settings = SimpleNamespace(
        openrouter_api_key="",
        openrouter_base_url="https://openrouter.ai/api/v1",
        config={"system_one": {"enabled": True, "model": "typesafe/jev-1.13"}},
    )
    client = build_system_one_client(settings)
    assert isinstance(client, OpenRouterSystemOneClient)


def test_missing_config_block_is_disabled():
    settings = SimpleNamespace(openrouter_api_key="sk", config={})
    assert isinstance(build_system_one_client(settings), DisabledSystemOneClient)


async def test_enabled_blank_key_evaluate_skips_without_crash():
    settings = SimpleNamespace(
        openrouter_api_key="",
        openrouter_base_url="https://openrouter.ai/api/v1",
        config={"system_one": {"enabled": True, "model": "typesafe/jev-1.13"}},
    )
    client = build_system_one_client(settings)
    with patch("ze_core.openrouter.system_one.httpx.AsyncClient") as mock_cls:
        result = await client.evaluate("hello", _QUESTIONS)
    assert result.skip_reason == "missing_key"
    mock_cls.assert_not_called()
