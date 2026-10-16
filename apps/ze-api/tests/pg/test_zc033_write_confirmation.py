import uuid

import pytest

pytestmark = pytest.mark.pg


async def test_milestone_columns_match_write_confirmation(pg_pool):
    async with pg_pool.acquire() as conn:
        columns = {
            row["column_name"]
            for row in await conn.fetch(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'goal_milestones'
                """
            )
        }
    assert "intent" not in columns
    assert "approved_writes" in columns


async def test_held_execution_and_held_write_row_round_trip(pg_pool):
    request_id = f"req-{uuid.uuid4().hex}"
    async with pg_pool.acquire() as conn:
        workflow_id = await conn.fetchval(
            """
            INSERT INTO workflows (name, description, steps)
            VALUES ($1, 'zc033 test', '[]'::jsonb)
            RETURNING id
            """,
            f"zc033-{uuid.uuid4().hex}",
        )
        execution_id = await conn.fetchval(
            """
            INSERT INTO workflow_executions (workflow_id, status)
            VALUES ($1, 'held')
            RETURNING id
            """,
            workflow_id,
        )
        await conn.execute(
            """
            INSERT INTO held_writes (request_id, source, owner_ref, items, payload, expires_at)
            VALUES ($1, 'workflow', $2, '[]'::jsonb, '{}'::jsonb, now() + interval '24 hours')
            """,
            request_id,
            str(execution_id),
        )
        row = await conn.fetchrow(
            "SELECT source, owner_ref, status, decided_at FROM held_writes WHERE request_id = $1",
            request_id,
        )
        status = await conn.fetchval(
            "SELECT status FROM workflow_executions WHERE id = $1", execution_id
        )

    assert row["source"] == "workflow"
    assert row["owner_ref"] == str(execution_id)
    assert row["status"] == "open"
    assert row["decided_at"] is None
    assert status == "held"
