from unittest.mock import AsyncMock

from ze_memory.extractor import (
    admit_family,
    extract_facts,
    is_trivial_turn,
    parse_fact_response,
)


def test_trivial_greeting_is_trivial():
    assert is_trivial_turn("ok")
    assert is_trivial_turn("thanks")
    assert is_trivial_turn("hello!")
    assert is_trivial_turn("")


def test_preference_after_ok_is_not_trivial():
    assert not is_trivial_turn("ok I prefer dark mode")


def test_admit_family_keep_drop():
    assert admit_family("preference") == "preference"
    assert admit_family("IDENTITY") == "identity"
    assert admit_family("commitment") is None
    assert admit_family("ephemeral") is None
    assert admit_family("drop") is None
    assert admit_family("city") is None


def test_parse_drops_commitment_and_ephemeral():
    assert parse_fact_response(
        '{"family": "commitment", "facts": [{"value": "call Mom Tuesday"}]}'
    ) == []
    assert parse_fact_response(
        '{"family": "ephemeral", "facts": [{"value": "tired today"}]}'
    ) == []


def test_parse_keeps_preference_and_constraint():
    prefs = parse_fact_response(
        '{"family": "preference", "facts": [{"value": "dark mode", "confidence": 0.9}]}'
    )
    assert prefs == [
        {"predicate": "preference", "value": "dark mode", "confidence": 0.9}
    ]
    constraints = parse_fact_response(
        '{"family": "constraint", "facts": [{"value": "allergic to peanuts"}]}'
    )
    assert constraints[0]["predicate"] == "constraint"


async def test_extract_facts_skips_trivial_prompt():
    client = AsyncMock()
    facts = await extract_facts(client, prompt="ok", response="sure", model="m")
    assert facts == []
    client.complete.assert_not_awaited()


async def test_extract_facts_empty_object_returns_empty():
    client = AsyncMock()
    client.complete = AsyncMock(return_value='{"family": "drop", "facts": []}')
    facts = await extract_facts(
        client, prompt="I'll call Mom Tuesday", response="ok", model="m"
    )
    assert facts == []
