from unittest.mock import AsyncMock

from ze.tools.contacts import _parse, _safe_classification, extract_contacts


# ── _safe_classification ──────────────────────────────────────────────────────

def test_safe_classification_valid():
    assert _safe_classification("personal") == "personal"
    assert _safe_classification("professional") == "professional"


def test_safe_classification_invalid_defaults():
    assert _safe_classification("executive") == "unknown"
    assert _safe_classification(None) == "unknown"


# ── _parse ────────────────────────────────────────────────────────────────────

def test_parse_valid_json():
    raw = '[{"name": "João Silva", "classification": "professional", "relationship": "charter operator", "contact_info": {}, "confidence": 0.9}]'
    result = _parse(raw)

    assert len(result) == 1
    assert result[0]["name"] == "João Silva"
    assert result[0]["classification"] == "professional"
    assert result[0]["confidence"] == 0.9


def test_parse_strips_markdown_fences():
    raw = '```json\n[{"name": "Maria", "classification": "personal", "relationship": "friend", "contact_info": {}, "confidence": 0.8}]\n```'
    result = _parse(raw)

    assert len(result) == 1
    assert result[0]["name"] == "Maria"


def test_parse_filters_below_confidence_threshold():
    raw = '[{"name": "Vague Person", "classification": "unknown", "relationship": "", "contact_info": {}, "confidence": 0.5}]'
    result = _parse(raw)

    assert result == []


def test_parse_filters_empty_names():
    raw = '[{"name": "", "classification": "unknown", "relationship": "", "contact_info": {}, "confidence": 0.9}]'
    result = _parse(raw)

    assert result == []


def test_parse_returns_empty_on_invalid_json():
    assert _parse("not json") == []
    assert _parse("{}") == []
    assert _parse("") == []


def test_parse_returns_empty_array_passthrough():
    assert _parse("[]") == []


def test_parse_defaults_unknown_classification():
    raw = '[{"name": "Jane", "classification": "CEO", "relationship": "boss", "contact_info": {}, "confidence": 0.9}]'
    result = _parse(raw)

    assert result[0]["classification"] == "unknown"


def test_parse_includes_contact_info():
    raw = '[{"name": "João", "classification": "professional", "relationship": "broker", "contact_info": {"email": "joao@example.com", "company": "AirLisboa"}, "confidence": 0.9}]'
    result = _parse(raw)

    assert result[0]["contact_info"]["email"] == "joao@example.com"
    assert result[0]["contact_info"]["company"] == "AirLisboa"


# ── extract_contacts tool ─────────────────────────────────────────────────────

async def test_extract_contacts_returns_tool_call_on_success():
    client = AsyncMock()
    client.complete = AsyncMock(return_value='[{"name": "João Silva", "classification": "professional", "relationship": "charter operator", "contact_info": {}, "confidence": 0.9}]')

    tc = await extract_contacts(
        prompt="I met João Silva today, he runs a charter company in Lisbon.",
        response="That sounds like a great lead for your discovery interviews.",
        client=client,
        model="anthropic/claude-haiku-4-5",
    )

    assert tc.success is True
    assert tc.tool_name == "extract_contacts"
    assert len(tc.result) == 1
    assert tc.result[0]["name"] == "João Silva"


async def test_extract_contacts_returns_empty_on_llm_failure():
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=Exception("timeout"))

    tc = await extract_contacts(
        prompt="...",
        response="...",
        client=client,
        model="anthropic/claude-haiku-4-5",
    )

    assert tc.success is False
    assert tc.result == []
    assert tc.error is not None


async def test_extract_contacts_returns_empty_list_passthrough():
    client = AsyncMock()
    client.complete = AsyncMock(return_value="[]")

    tc = await extract_contacts(
        prompt="How's the weather?",
        response="It's sunny today.",
        client=client,
        model="anthropic/claude-haiku-4-5",
    )

    assert tc.success is True
    assert tc.result == []
