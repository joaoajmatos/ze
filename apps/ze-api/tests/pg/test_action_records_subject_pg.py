from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from ze_memory.action_records.store import PostgresActionRecordStore
from ze_memory.action_records.types import ActionSubjectKind

pytestmark = pytest.mark.pg

T0 = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)


async def _insert(pool, *, context, occurred_at, key=None, lifecycle="succeeded"):
    outcome = None if lifecycle == "started" else "success"
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO action_records (
                id, idempotency_key, action_type, actor, producer_plugin,
                lifecycle, outcome, occurred_at, provenance, confidence,
                target_face, summary, authoritative_domain,
                authoritative_record_id, context
            ) VALUES (
                $1, $2, 'test.act', 'tester', 'ze-test', $3, $4, $5, 'prompt_supplied',
                1.0, 'world', 'did a thing', 'test', 'x', $6::jsonb
            ) RETURNING id
            """,
            uuid4(),
            key or str(uuid4()),
            lifecycle,
            outcome,
            occurred_at,
            context,
        )


@pytest.fixture
async def ledger(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE action_records CASCADE")
    return PostgresActionRecordStore(pg_pool)


async def test_goal_filter_newest_first_and_empty_context(pg_pool, ledger):
    g1, g2, run = uuid4(), uuid4(), uuid4()
    a = await _insert(pg_pool, context=f'{{"goal_id": "{g1}"}}', occurred_at=T0)
    b = await _insert(
        pg_pool, context=f'{{"goal_id": "{g1}"}}', occurred_at=T0 + timedelta(hours=1)
    )
    await _insert(pg_pool, context=f'{{"goal_id": "{g2}"}}', occurred_at=T0)
    await _insert(pg_pool, context=f'{{"workflow_run_id": "{run}"}}', occurred_at=T0)
    await _insert(pg_pool, context="{}", occurred_at=T0)

    got = await ledger.list_by_subject(kind=ActionSubjectKind.GOAL, subject_id=g1)
    assert [r.id for r in got] == [b, a]

    everything = await ledger.list_by_subject()
    assert len(everything) == 5


async def test_workflow_lists_started_and_finished(pg_pool, ledger):
    wf, run = uuid4(), uuid4()
    ctx = f'{{"workflow_id": "{wf}", "workflow_run_id": "{run}"}}'
    started = await _insert(pg_pool, context=ctx, occurred_at=T0, lifecycle="started")
    finished = await _insert(
        pg_pool, context=ctx, occurred_at=T0 + timedelta(minutes=1)
    )
    got = await ledger.list_by_subject(kind=ActionSubjectKind.WORKFLOW, subject_id=wf)
    assert [r.id for r in got] == [finished, started]
    by_run = await ledger.list_by_subject(
        kind=ActionSubjectKind.WORKFLOW_RUN, subject_id=run
    )
    assert {r.id for r in by_run} == {started, finished}


async def test_paging_walks_everything_with_tied_timestamps(pg_pool, ledger):
    g = uuid4()
    ids = [
        await _insert(
            pg_pool,
            context=f'{{"goal_id": "{g}"}}',
            occurred_at=T0 + timedelta(hours=min(i, 2)),
        )
        for i in range(5)
    ]
    seen, cursor = [], None
    while True:
        page = await ledger.list_by_subject(
            kind=ActionSubjectKind.GOAL, subject_id=g, cursor=cursor, limit=1
        )
        if not page:
            break
        seen.append(page[0].id)
        cursor = (page[0].occurred_at, page[0].id)
    assert len(seen) == 5 and set(seen) == set(ids)


async def test_since_excludes_older(pg_pool, ledger):
    g = uuid4()
    await _insert(pg_pool, context=f'{{"goal_id": "{g}"}}', occurred_at=T0)
    new = await _insert(
        pg_pool, context=f'{{"goal_id": "{g}"}}', occurred_at=T0 + timedelta(days=2)
    )
    got = await ledger.list_by_subject(
        kind=ActionSubjectKind.GOAL, subject_id=g, since=T0 + timedelta(days=1)
    )
    assert [r.id for r in got] == [new]
