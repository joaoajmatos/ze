from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from ze_automation.workflow.postgres import PostgresWorkflowStore

pytestmark = pytest.mark.pg


async def _workflow(pool, name):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO workflows (name, description, steps) VALUES ($1, 'd', '[]'::jsonb) RETURNING id",
            name,
        )


async def _execution(pool, workflow_id, status, completed_ago, error=None):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO workflow_executions (workflow_id, status, error, completed_at)
            VALUES ($1, $2, $3, $4) RETURNING id
            """,
            workflow_id,
            status,
            error,
            datetime.now(timezone.utc) - completed_ago,
        )


async def test_lists_recent_failures_newest_first(pg_pool):
    name = f"wf-{uuid4()}"
    wf = await _workflow(pg_pool, name)
    newer = await _execution(pg_pool, wf, "failed", timedelta(minutes=10), "boom")
    older = await _execution(pg_pool, wf, "failed", timedelta(minutes=30))
    ok = await _execution(pg_pool, wf, "completed", timedelta(minutes=5))
    old = await _execution(pg_pool, wf, "failed", timedelta(days=3))
    orphan = await _execution(pg_pool, None, "failed", timedelta(minutes=20))

    failures = await PostgresWorkflowStore(pg_pool).list_failed_executions(24)

    mine = [f for f in failures if f.execution_id in {newer, older, ok, old, orphan}]
    assert [f.execution_id for f in mine] == [newer, orphan, older]
    assert mine[0].workflow_name == name
    assert mine[0].workflow_id == wf
    assert mine[0].error == "boom"
    assert mine[1].workflow_name == "unknown"
    assert mine[1].workflow_id is None


async def test_lists_a_run_failed_by_stale_recovery(pg_pool):
    wf = await _workflow(pg_pool, f"wf-{uuid4()}")
    async with pg_pool.acquire() as conn:
        exec_id = await conn.fetchval(
            """
            INSERT INTO workflow_executions (workflow_id, status, started_at)
            VALUES ($1, 'running', now() - interval '2 hours') RETURNING id
            """,
            wf,
        )
    store = PostgresWorkflowStore(pg_pool)
    await store.recover_stale(timeout_minutes=30)

    failures = await store.list_failed_executions(24)

    assert exec_id in {f.execution_id for f in failures}
