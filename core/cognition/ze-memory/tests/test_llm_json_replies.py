import json
from unittest.mock import AsyncMock

import pytest

from ze_memory.extractor import (
    extract_entities,
    parse_event_response,
    parse_fact_response,
    write_fact_values,
)
from ze_memory.synthesizer import ProfileSynthesizer

WRAPS = [
    pytest.param(lambda s: s, id="bare"),
    pytest.param(lambda s: f"```json\n{s}\n```", id="fenced"),
    pytest.param(
        lambda s: f"Sure, here you go:\n```json\n{s}\n```\nAnything else?", id="prose"
    ),
    pytest.param(lambda s: f"Result: {s} — hope it helps", id="inline-prose"),
]


@pytest.mark.parametrize("wrap", WRAPS)
def test_parse_fact_response(wrap):
    raw = wrap(json.dumps([{"predicate": "preference", "value": "tea", "confidence": 0.9}]))
    assert parse_fact_response(raw)


@pytest.mark.parametrize("wrap", WRAPS)
def test_parse_event_response(wrap):
    raw = wrap(json.dumps([{"title": "Dinner", "event_type": "social"}]))
    assert parse_event_response(raw) == [{"title": "Dinner", "event_type": "social"}]


def test_parse_event_response_garbage_is_empty():
    assert parse_event_response("nothing structured") == []


@pytest.mark.parametrize("wrap", WRAPS)
async def test_extract_entities(wrap):
    client = AsyncMock()
    client.complete.return_value = wrap(
        json.dumps([{"name": "Ana", "entity_type": "person"}])
    )
    entities = await extract_entities(client, prompt="p", response="r", model="m")
    assert [e.canonical_name for e in entities] == ["Ana"]


@pytest.mark.parametrize("wrap", WRAPS)
async def test_write_fact_values(wrap):
    client = AsyncMock()
    client.complete.return_value = wrap(json.dumps({"facts": [{"value": "Likes tea"}]}))
    facts = await write_fact_values(
        client, prompt="p", response="r", family="preference", model="m"
    )
    assert len(facts) == 1


@pytest.mark.parametrize("wrap", WRAPS)
async def test_profile_synthesizer(wrap):
    store = AsyncMock()
    store.fetch_active_fact_summaries.return_value = [
        {"predicate": "likes", "value": "tea"}
    ]
    store.fetch_recent_episode_summaries.return_value = []
    client = AsyncMock()
    client.complete.return_value = wrap(
        json.dumps(
            [{"key": "drink", "value": "tea", "stability": "stable", "confidence": 0.9}]
        )
    )
    synth = ProfileSynthesizer(store, client)
    assert await synth.update_profile() is True
