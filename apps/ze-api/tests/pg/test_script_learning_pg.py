from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from ze_agents.scripts import ScriptOutcome
from ze_memory.action_records.store import PostgresActionRecordStore
from ze_api.wiring.db import _init_conn
from ze_workspace.script_learning import ScriptLearning, tool_signature

pytestmark = pytest.mark.pg


@pytest_asyncio.fixture
async def app_pool(pg_dsn):
    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=2, init=_init_conn)
    yield pool
    await pool.close()


async def test_three_runs_of_one_key_leave_three_rows_newest_first(app_pool):
    pg_pool = app_pool
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE action_records CASCADE")
    store = PostgresActionRecordStore(pg_pool)

    class NoAdmission:
        async def candidate_exists(self, name):
            return True

        async def submit_procedure_candidate(self, candidate):
            raise AssertionError("candidate_exists is true")

    learning = ScriptLearning(action_record_store=store, admission=NoAdmission())
    ids = [str(uuid4()) for _ in range(3)]
    for script_id in ids:
        await learning.record(
            script_id=script_id,
            agent="finance",
            source="z.finish(1)",
            outcome=ScriptOutcome(status="ok"),
            tools=["get_a", "get_b"],
        )
    key = tool_signature("finance", ["get_a", "get_b"])
    async with pg_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM action_records WHERE context->>'script_key' = $1", key
        )
    assert count == 3
    async with pg_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO action_records (
                id, idempotency_key, action_type, actor, producer_plugin,
                lifecycle, outcome, occurred_at, provenance, confidence,
                target_face, summary, authoritative_domain,
                authoritative_record_id, context
            ) VALUES (
                $1, 'other', 'test.act', 't', 'p', 'succeeded', 'success', now(),
                'prompt_supplied', 1.0, 'world', 's', 'elsewhere', 'x', $2::jsonb
            )
            """,
            uuid4(),
            {"script_key": key},
        )
    rows = await store.list_by_script_key(key)
    assert [r.authoritative_ref.record_id for r in rows] == list(reversed(ids))
    assert all(r.context.script_key == key for r in rows)
