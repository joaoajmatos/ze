from unittest.mock import AsyncMock

import pytest

from ze_core.memory.extractor import (
    extract_user_facts,
    gather_fact_proposals,
    merge_fact_proposals,
    parse_fact_response,
)
from ze_core.memory.types import UserFact


def test_parse_fact_response_strips_markdown_fence():
    raw = '```json\n[{"key": "city", "value": "Lisbon", "confidence": 0.9}]\n```'
    assert parse_fact_response(raw) == [{"key": "city", "value": "Lisbon", "confidence": 0.9}]


def test_parse_fact_response_invalid_returns_empty():
    assert parse_fact_response("not json") == []
    assert parse_fact_response('{"key": "x"}') == []


def test_merge_explicit_overrides_extracted():
    extracted = [UserFact(key="city", value="Porto", agent="global")]
    explicit = [UserFact(key="city", value="Lisbon", agent="global")]
    merged = merge_fact_proposals(explicit, extracted)
    assert len(merged) == 1
    assert merged[0].value == "Lisbon"


@pytest.mark.asyncio
async def test_extract_user_facts_skips_error_responses():
    client = AsyncMock()
    facts = await extract_user_facts(
        client, prompt="hi", response="[ERROR] boom", model="m"
    )
    assert facts == []
    client.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_gather_fact_proposals_merges_llm_output():
    client = AsyncMock()
    client.complete = AsyncMock(return_value='[{"key": "lang", "value": "Python"}]')
    configurable = {"openrouter_client": client, "settings": None}
    proposals = await gather_fact_proposals(
        configurable,
        agent="companion",
        prompt="I love Python",
        response="Great choice!",
        explicit=[],
    )
    assert len(proposals) == 1
    assert proposals[0].key == "lang"


@pytest.mark.asyncio
async def test_gather_without_client_returns_explicit_only():
    explicit = [UserFact(key="name", value="João", agent="global")]
    proposals = await gather_fact_proposals(
        {},
        agent="companion",
        prompt="hi",
        response="hello",
        explicit=explicit,
    )
    assert proposals == explicit
