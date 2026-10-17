import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from ze_correlation.store import PostgresHypothesisStore

pytestmark = pytest.mark.pg

UTC = timezone.utc


async def _insert(pool, summary, *, entities=(), confirmed=False, feedback=None, age_h=1):
    hid = uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO correlation_hypothesis
              (id, summary, narrative, relation, confidence, relevance, evidence,
               entities, surfaced, feedback, created_at, claim_kind, confirmed)
            VALUES ($1, $2, 'n', 'pattern', 0.5, 0.5, '[]'::jsonb, $3::jsonb,
                    false, $4, $5, 'inference', $6)
            """,
            hid,
            summary,
            json.dumps([str(e) for e in entities]),
            feedback,
            datetime.now(UTC) - timedelta(hours=age_h),
            confirmed,
        )
    return hid


async def test_states_entity_filter_and_dismissal(pg_pool):
    store = PostgresHypothesisStore(pg_pool)
    e1, e2 = uuid4(), uuid4()
    await _insert(pg_pool, "open", entities=[e1], age_h=1)
    await _insert(pg_pool, "useful", entities=[e1], feedback="useful", age_h=2)
    muted = await _insert(pg_pool, "muted", entities=[e1], feedback="muted", age_h=3)
    await _insert(pg_pool, "conf-muted", entities=[e1], confirmed=True, feedback="muted", age_h=4)
    await _insert(pg_pool, "elsewhere", entities=[e2], age_h=5)

    def names(rows):
        return [h.summary for h in rows]

    assert names(await store.list_for_display(entity_id=None, state="open", limit=10)) == [
        "open", "useful", "elsewhere"
    ]
    assert names(await store.list_for_display(entity_id=e1, state="open", limit=10)) == [
        "open", "useful"
    ]
    assert names(await store.list_for_display(entity_id=None, state="confirmed", limit=10)) == ["conf-muted"]
    assert names(await store.list_for_display(entity_id=None, state="dismissed", limit=10)) == ["muted"]
    assert len(await store.list_for_display(entity_id=None, state="all", limit=10)) == 5

    assert "muted" not in names(await store.list_unsurfaced())
    assert "muted" not in names(await store.list_recent(30))
    assert "muted" not in names(await store.list_by_entities([e1]))
    assert "muted" in names(await store.list_by_entities([e1], include_dismissed=True))

    await store.set_feedback(muted, None)
    assert "muted" in names(await store.list_unsurfaced())
    assert "muted" in names(await store.list_by_entities([e1]))
