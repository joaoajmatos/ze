from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from ze_agents.types import RetrievalRequest
from ze_memory.policies import CompanionPolicy


def _fact_row(*, similarity, reviewed: bool, predicate: str, value: str):
    return {
        "id": uuid4(),
        "subject_id": None,
        "predicate": predicate,
        "object_text": None,
        "object_id": None,
        "value": value,
        "confidence": 0.9,
        "reviewed": reviewed,
        "contradicted": False,
        "source_episode_id": None,
        "source_refs": "[]",
        "provenance": "prompt_supplied",
        "claim_kind": "fact",
        "similarity": similarity,
        "created_at": None,
    }


def _async_ctx(conn):
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@patch("ze_memory.policies._fetch_reviewed_facts", new_callable=AsyncMock)
@patch("ze_memory.policies._fetch_session_summary_rows", new_callable=AsyncMock)
@patch("ze_memory.policies._fetch_events_by_similarity", new_callable=AsyncMock)
@patch("ze_memory.policies._fetch_entities_by_similarity", new_callable=AsyncMock)
@patch("ze_memory.policies._fetch_facts_by_similarity", new_callable=AsyncMock)
async def test_reviewed_facts_are_present_despite_low_similarity(
    mock_facts, mock_entities, mock_events, mock_summaries, mock_reviewed
):
    reviewed = _fact_row(
        similarity=0.05,
        reviewed=True,
        predicate="identity",
        value="name is João",
    )
    junk = _fact_row(
        similarity=0.1,
        reviewed=False,
        predicate="preference",
        value="likes quarterly report templates",
    )
    relevant = _fact_row(
        similarity=0.9,
        reviewed=False,
        predicate="preference",
        value="likes espresso",
    )
    mock_reviewed.return_value = [reviewed]
    mock_facts.return_value = [relevant, junk]
    mock_entities.return_value = []
    mock_events.return_value = []
    mock_summaries.return_value = []

    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[[], []])
    store = MagicMock()
    store.pool = MagicMock()
    store.pool.acquire = MagicMock(return_value=_async_ctx(conn))
    store.settings = {"memory": {"relevance_floor": 0.35}}
    store.graph_store = None

    ctx = await CompanionPolicy().retrieve(
        RetrievalRequest(
            module="companion",
            agent="companion",
            query_text="espresso",
            query_embedding=[0.1, 0.2, 0.3],
            current_session_id="s1",
        ),
        store,
    )
    values = [f.value for f in ctx.facts]
    assert "name is João" in values
    assert "likes espresso" in values
    assert "likes quarterly report templates" not in values
