import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_personal.contacts.consolidator import ContactsConsolidator

_PAYLOAD = {
    "people": [{"name": "Ana", "classification": "friend", "relationship": "friend"}],
    "projects": [],
    "relationships": [],
}

WRAPS = [
    pytest.param(lambda s: s, id="bare"),
    pytest.param(lambda s: f"```json\n{s}\n```", id="fenced"),
    pytest.param(lambda s: f"Here you go:\n```json\n{s}\n```\nDone.", id="prose"),
    pytest.param(lambda s: f"Result: {s} (end)", id="inline-prose"),
]


@pytest.mark.parametrize("wrap", WRAPS)
async def test_extract_candidates_tolerates_fenced_and_prose_replies(wrap):
    client = MagicMock()
    client.complete = AsyncMock(return_value=wrap(json.dumps(_PAYLOAD)))
    consolidator = ContactsConsolidator(
        pool=MagicMock(), person_store=MagicMock(), openrouter_client=client
    )
    batch = [
        {
            "id": 1,
            "created_at": datetime(2025, 1, 1),
            "prompt": "I met Ana",
            "summary": "Met Ana",
            "response": "ok",
        }
    ]

    people, projects, edges = await consolidator._extract_candidates(batch)

    assert [p.name for p in people] == ["Ana"]
