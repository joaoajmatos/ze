"""Tests for ze_memory.extractor — event extraction functions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest


from ze_memory.extractor import (
    TurnProposals,
    extract_facts,
    extract_turn_graph,
    gather_fact_proposals,
    gather_turn_proposals,
    parse_event_response,
    parse_fact_response,
    raw_to_events,
)
from ze_memory.types import Event


# ── parse_event_response ──────────────────────────────────────────────────────


def test_parse_event_response_valid_list():
    raw = json.dumps(
        [
            {"title": "Team meeting", "event_type": "meeting"},
            {
                "title": "Dentist",
                "event_type": "appointment",
                "start_at": "2024-03-10T10:00:00",
            },
        ]
    )
    result = parse_event_response(raw)
    assert len(result) == 2
    assert result[0]["title"] == "Team meeting"


def test_parse_event_response_strips_markdown_fence():
    raw = '```json\n[{"title": "Call", "event_type": "call"}]\n```'
    result = parse_event_response(raw)
    assert len(result) == 1
    assert result[0]["title"] == "Call"


def test_parse_event_response_drops_items_without_title():
    raw = json.dumps(
        [
            {"event_type": "meeting"},
            {"title": "Valid", "event_type": "call"},
        ]
    )
    result = parse_event_response(raw)
    assert len(result) == 1
    assert result[0]["title"] == "Valid"


def test_parse_event_response_drops_items_without_event_type():
    raw = json.dumps([{"title": "No type"}])
    result = parse_event_response(raw)
    assert result == []


def test_parse_event_response_returns_empty_on_invalid_json():
    result = parse_event_response("not json")
    assert result == []


def test_parse_event_response_returns_empty_on_non_list():
    result = parse_event_response(json.dumps({"title": "Not a list"}))
    assert result == []


# ── raw_to_events ─────────────────────────────────────────────────────────────


def test_raw_to_events_basic():
    raw = [{"title": "Sprint planning", "event_type": "meeting"}]
    events = raw_to_events(raw)
    assert len(events) == 1
    assert isinstance(events[0], Event)
    assert events[0].title == "Sprint planning"
    assert events[0].event_type == "meeting"
    assert events[0].id is None


def test_raw_to_events_with_timestamps():
    raw = [
        {
            "title": "Flight to Lisbon",
            "event_type": "trip",
            "start_at": "2024-06-01T08:00:00Z",
            "end_at": "2024-06-01T10:00:00Z",
        }
    ]
    events = raw_to_events(raw)
    assert events[0].start_at is not None
    assert events[0].end_at is not None


def test_raw_to_events_with_participants():
    raw = [{"title": "1:1", "event_type": "meeting", "participants": ["Alice", "Bob"]}]
    events = raw_to_events(raw)
    assert events[0].participant_names == ["Alice", "Bob"]


def test_raw_to_events_skips_invalid_items():
    raw = [
        {"event_type": "meeting"},
        {"title": "Valid", "event_type": "call"},
    ]
    events = raw_to_events(raw)
    assert len(events) == 1


def test_raw_to_events_empty_list():
    assert raw_to_events([]) == []


# ── extract_turn_graph ────────────────────────────────────────────────────────


def _turn_reply(events=None, entities=None) -> str:
    return json.dumps({"events": events or [], "entities": entities or []})


async def test_extract_turn_graph_makes_one_call_for_events_and_entities():
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=_turn_reply(
            events=[{"title": "Weekly sync", "event_type": "meeting"}],
            entities=[{"name": "Ana", "entity_type": "person"}],
        )
    )

    proposals = await extract_turn_graph(
        client,
        prompt="meeting notes",
        response="We had a weekly sync with Ana.",
        model="test",
    )

    client.complete.assert_called_once()
    assert [e.title for e in proposals.events] == ["Weekly sync"]
    assert [e.canonical_name for e in proposals.entities] == ["Ana"]


async def test_extract_turn_graph_skips_error_responses():
    client = AsyncMock()
    proposals = await extract_turn_graph(
        client, prompt="hi", response="[ERROR] something went wrong", model="test"
    )
    client.complete.assert_not_called()
    assert proposals == TurnProposals()


async def test_extract_turn_graph_returns_empty_on_llm_failure():
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
    proposals = await extract_turn_graph(
        client, prompt="hi", response="We met yesterday.", model="test"
    )
    assert proposals == TurnProposals()


async def test_extract_turn_graph_returns_empty_on_bad_json():
    client = AsyncMock()
    client.complete = AsyncMock(return_value="not json")
    proposals = await extract_turn_graph(
        client, prompt="hi", response="We met.", model="test"
    )
    assert proposals == TurnProposals()


async def test_extract_turn_graph_keeps_events_when_entities_are_malformed():
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=json.dumps(
            {
                "events": [{"title": "Dinner", "event_type": "meal"}],
                "entities": "oops",
            }
        )
    )
    proposals = await extract_turn_graph(
        client, prompt="p", response="Dinner was nice.", model="test"
    )
    assert [e.title for e in proposals.events] == ["Dinner"]
    assert proposals.entities == []


async def test_extract_turn_graph_drops_incomplete_items():
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=_turn_reply(
            events=[{"title": "no type"}],
            entities=[{"name": "no type either"}],
        )
    )
    proposals = await extract_turn_graph(client, prompt="p", response="r", model="m")
    assert proposals == TurnProposals()


# ── gather_turn_proposals ─────────────────────────────────────────────────────


async def test_gather_turn_proposals_with_client():
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=_turn_reply(
            events=[{"title": "Dinner with Alice", "event_type": "meal"}]
        )
    )
    proposals = await gather_turn_proposals(
        {"openrouter_client": client},
        prompt="I had dinner with Alice",
        response="Nice dinner with Alice.",
    )
    assert [e.title for e in proposals.events] == ["Dinner with Alice"]


async def test_gather_turn_proposals_without_client_returns_empty():
    assert await gather_turn_proposals({}, prompt="hi there", response="hello") == (
        TurnProposals()
    )


@pytest.mark.parametrize("prompt", ["hi", "Thanks!", "ok", "", "   "])
async def test_gather_turn_proposals_skips_trivial_turns(prompt):
    client = AsyncMock()
    proposals = await gather_turn_proposals(
        {"openrouter_client": client}, prompt=prompt, response="Hello! How can I help?"
    )
    client.complete.assert_not_called()
    assert proposals == TurnProposals()


async def test_gather_turn_proposals_uses_the_fact_extraction_model():
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_turn_reply())
    settings = type(
        "S", (), {"config": {"memory": {"fact_extraction_model": "cheap/model"}}}
    )()
    await gather_turn_proposals(
        {"openrouter_client": client, "settings": settings},
        prompt="I moved to Porto",
        response="Noted.",
    )
    assert client.complete.call_args.kwargs["model"] == "cheap/model"


# ── facts ─────────────────────────────────────────────────────────────────────


def test_parse_fact_response_strips_markdown_fence():
    raw = '```json\n{"family": "identity", "facts": [{"value": "Lisbon", "confidence": 0.9}]}\n```'
    assert parse_fact_response(raw) == [
        {"predicate": "identity", "value": "Lisbon", "confidence": 0.9}
    ]


def test_parse_fact_response_invalid_returns_empty():
    assert parse_fact_response("not json") == []
    assert parse_fact_response('{"key": "x"}') == []
    assert (
        parse_fact_response('{"family": "city", "facts": [{"value": "Lisbon"}]}') == []
    )


@pytest.mark.asyncio
async def test_extract_user_facts_skips_error_responses():
    client = AsyncMock()
    facts = await extract_facts(client, prompt="hi", response="[ERROR] boom", model="m")
    assert facts == []
    client.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_gather_fact_proposals_merges_llm_output():
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value='{"family": "preference", "facts": [{"value": "Python"}]}'
    )
    configurable = {"openrouter_client": client, "settings": None}
    proposals = await gather_fact_proposals(
        configurable,
        agent="companion",
        prompt="I love Python",
        response="Great choice!",
    )
    assert proposals.path == "haiku"
    assert len(proposals.facts) == 1
    assert proposals.facts[0].predicate == "preference"


@pytest.mark.asyncio
async def test_gather_without_client_returns_empty():
    proposals = await gather_fact_proposals(
        {},
        agent="companion",
        prompt="I love Python",
        response="hello",
    )
    assert proposals.facts == []
    assert proposals.path == "none"
