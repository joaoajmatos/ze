from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind, Provenance

from ze_correlation import rest
from ze_correlation.types import Hypothesis, HypothesisEvidence

NOW = datetime(2026, 10, 17, 9, tzinfo=timezone.utc)


def _hyp(entities, *, kind=ClaimKind.INFERENCE, **kw) -> Hypothesis:
    return Hypothesis(
        id=uuid4(),
        summary="Alice may work on Launch",
        narrative="reply and meeting co-occurrence",
        relation="pattern",
        confidence=0.6,
        relevance=0.5,
        evidence=[
            HypothesisEvidence(
                kind="episode",
                id=uuid4(),
                label="email reply Jan 3",
                external_ref=None,
                origin=Provenance.LIVE_SEARCH,
                retrieved_at=NOW,
            )
        ],
        entities=entities,
        created_at=NOW,
        claim_kind=kind,
        **kw,
    )


async def test_list_maps_fields_with_one_name_lookup_per_page():
    a, b, c = uuid4(), uuid4(), uuid4()
    h1, h2 = _hyp([a, b]), _hyp([b, c], confirmed=True)
    store = AsyncMock()
    store.list_for_display = AsyncMock(return_value=[h1, h2])
    names = AsyncMock(return_value={a: "Alice", b: "Launch"})

    items = await rest.list_hypotheses(
        store, names, entity_id=None, state="all", limit=10
    )

    names.assert_awaited_once()
    assert set(names.await_args.args[0]) == {a, b, c}
    first = items[0]
    assert first["id"] == h1.id
    assert first["claim_kind"] == "inference"
    assert first["evidence"] == [
        {"kind": "episode", "id": h1.evidence[0].id, "label": "email reply Jan 3"}
    ]
    assert first["entities"] == [
        {"id": a, "name": "Alice"},
        {"id": b, "name": "Launch"},
    ]
    assert first["created_at"] == NOW.isoformat()
    assert items[1]["confirmed"] is True
    store.list_for_display.assert_awaited_once_with(
        entity_id=None, state="all", limit=10
    )


async def test_missing_entity_has_null_name():
    a = uuid4()
    store = AsyncMock()
    store.list_for_display = AsyncMock(return_value=[_hyp([a])])
    [item] = await rest.list_hypotheses(
        store, AsyncMock(return_value={}), entity_id=None, state="open", limit=5
    )
    assert item["entities"] == [{"id": a, "name": None}]


async def test_row_with_a_fact_claim_kind_is_skipped():
    store = AsyncMock()
    store.list_for_display = AsyncMock(
        return_value=[_hyp([], kind=ClaimKind.FACT), _hyp([], kind=ClaimKind.SUSPICION)]
    )
    items = await rest.list_hypotheses(
        store, AsyncMock(return_value={}), entity_id=None, state="all", limit=5
    )
    assert [i["claim_kind"] for i in items] == ["suspicion"]


async def test_set_feedback_returns_the_mapped_row():
    a = uuid4()
    h = _hyp([a], feedback="muted")
    store = AsyncMock()
    store.set_feedback = AsyncMock(return_value=h)
    item = await rest.set_feedback(
        store, AsyncMock(return_value={a: "Alice"}), h.id, "muted"
    )
    store.set_feedback.assert_awaited_once_with(h.id, "muted")
    assert item["feedback"] == "muted"
    assert item["entities"][0]["name"] == "Alice"
