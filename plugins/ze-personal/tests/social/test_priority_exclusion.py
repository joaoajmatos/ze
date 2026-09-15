"""Regression test for FR-010 (spec 130): unconfirmed co-occurrence
hypotheses must never consume the shared attention budget.

`PersonStore.list_stale_for_follow_up()` — the only thing `PriorityView`'s
`RelationshipStalenessSource` wiring calls — queries the `contacts` table
only. Phase 130 introduces no wiring path from `correlation_hypothesis` into
`PriorityView`/`push_log`; this test locks that absence in so a future change
can't accidentally add one without failing here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from ze_personal.contacts.store import PersonStore


async def test_list_stale_for_follow_up_only_queries_contacts_table():
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    class _Ctx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *_):
            pass

    pool.acquire = lambda: _Ctx()
    store = PersonStore(pool=pool, memory_store=None)

    await store.list_stale_for_follow_up(stale_days=14, limit=10)

    sql = conn.fetch.call_args[0][0]
    assert "FROM contacts" in sql
    assert "correlation_hypothesis" not in sql


def test_social_cooccurrence_job_never_touches_push_log():
    """`SocialCooccurrenceJob` has no `push_log`/budget dependency at all —
    if it ever grows one, this constructor-signature check catches the drift
    before FR-010 silently regresses."""
    import inspect

    from ze_personal.jobs.social_cooccurrence import SocialCooccurrenceJob

    params = inspect.signature(SocialCooccurrenceJob.__init__).parameters
    assert "push_log" not in params
    assert "push_log_store" not in params
