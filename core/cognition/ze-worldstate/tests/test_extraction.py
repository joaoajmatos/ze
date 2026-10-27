from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_worldstate.decision import CommitDecision
from ze_worldstate.extraction import decide_with_109_gate, resolve_entities


def _llm(response: dict) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=json.dumps(response))
    return client


async def _decide(response: dict) -> CommitDecision:
    return await decide_with_109_gate("some text", _llm(response), "model")


async def test_ordinary_content_holds():
    decision = await _decide({"is_loop": False, "title": ""})
    assert (decision.kind, decision.reason) == ("hold", "gate_not_loop")


async def test_a_loop_without_a_title_holds():
    decision = await _decide({"is_loop": True, "title": ""})
    assert decision.kind == "hold"


async def test_an_implied_loop_is_a_suspected_create_with_its_title_and_window():
    decision = await _decide(
        {"is_loop": True, "title": "Renew passport", "implied_window_days": 5}
    )
    assert decision == CommitDecision(
        "create_suspected", "gate_implied", title="Renew passport", window_days=5
    )


async def test_an_explicit_declaration_is_a_declared_create():
    decision = await _decide(
        {
            "is_loop": True,
            "title": "Follow up with the accountant",
            "explicit_declaration": True,
        }
    )
    assert (decision.kind, decision.title, decision.window_days) == (
        "create_declared",
        "Follow up with the accountant",
        None,
    )


async def test_resolves_existing_is_a_resolve_with_the_gate_title():
    decision = await _decide(
        {
            "is_loop": False,
            "title": "Follow up with the accountant",
            "resolves_existing": True,
        }
    )
    assert (decision.kind, decision.title) == (
        "resolve",
        "Follow up with the accountant",
    )


async def test_resolves_without_a_title_holds():
    decision = await _decide({"is_loop": False, "title": "", "resolves_existing": True})
    assert decision.kind == "hold"


async def test_a_resolve_wins_over_a_loop_flag():
    decision = await _decide(
        {"is_loop": True, "title": "Pay rent", "resolves_existing": True}
    )
    assert decision.kind == "resolve"


@pytest.mark.parametrize("exc", [RuntimeError("down"), ValueError("no JSON")])
async def test_a_failed_gate_holds_with_gate_failed(exc):
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=exc)
    decision = await decide_with_109_gate("text", client, "model")
    assert (decision.kind, decision.reason) == ("hold", "gate_failed")


async def test_an_unparseable_reply_holds_with_gate_failed():
    client = AsyncMock()
    client.complete = AsyncMock(return_value="sorry, no")
    decision = await decide_with_109_gate("text", client, "model")
    assert (decision.kind, decision.reason) == ("hold", "gate_failed")


async def test_fenced_haiku_reply_still_decides():
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value='```json\n{"is_loop": true, "title": "Renew passport"}\n```'
    )
    decision = await decide_with_109_gate("text", client, "model")
    assert (decision.kind, decision.title) == ("create_suspected", "Renew passport")


async def test_the_gate_never_returns_fallback():
    for response in (
        {"is_loop": False},
        {"is_loop": True, "title": "x"},
        {"is_loop": True, "title": "x", "explicit_declaration": True},
        {"resolves_existing": True, "title": "x"},
    ):
        assert (await _decide(response)).kind != "fallback"


async def test_resolve_entities_is_public_and_swallows_resolver_errors():
    ids = [uuid4()]
    assert await resolve_entities(AsyncMock(return_value=ids), "text") == ids
    assert await resolve_entities(None, "text") == []
    assert await resolve_entities(AsyncMock(side_effect=RuntimeError("x")), "t") == []
