import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from ze_memory.action_records.store import PostgresActionRecordStore
from ze_memory.action_records.types import ActionSubjectKind
from ze_memory.migrations.versions import zm025_action_records_json_repair as zm025

pytestmark = pytest.mark.pg


async def _insert_string_shaped(conn, goal_id):
    await conn.execute(
        """
        INSERT INTO action_records (
            id, idempotency_key, action_type, actor, producer_plugin,
            lifecycle, outcome, occurred_at, provenance, confidence,
            target_face, summary, authoritative_domain, authoritative_record_id,
            context, evidence, causal_refs
        ) VALUES (
            $1, $2, 'goal.milestone', 'a', 'p', 'succeeded', 'success', $3,
            'synthesized', 1.0, 'world', 's', 'd', 'r',
            to_jsonb($4::text), to_jsonb($5::text), to_jsonb($6::text)
        )
        """,
        uuid4(),
        str(uuid4()),
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        json.dumps({"goal_id": str(goal_id)}),
        json.dumps([{"kind": "goal", "id": str(goal_id)}]),
        json.dumps([]),
    )


async def test_repair_unwraps_strings_and_makes_the_subject_filter_match(pg_pool):
    goal_id = uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE action_records CASCADE")
        await _insert_string_shaped(conn, goal_id)
    store = PostgresActionRecordStore(pg_pool)
    before = await store.list_by_subject(kind=ActionSubjectKind.GOAL, subject_id=goal_id)
    assert before == []

    async with pg_pool.acquire() as conn:
        await conn.execute(zm025.REPAIR_SQL)
        types = await conn.fetchrow(
            "SELECT jsonb_typeof(context) c, jsonb_typeof(evidence) e, "
            "jsonb_typeof(causal_refs) r FROM action_records"
        )
    assert (types["c"], types["e"], types["r"]) == ("object", "array", "array")
    after = await store.list_by_subject(kind=ActionSubjectKind.GOAL, subject_id=goal_id)
    assert len(after) == 1


async def test_repair_leaves_well_formed_rows_alone(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("TRUNCATE action_records CASCADE")
        await conn.execute(
            """
            INSERT INTO action_records (
                id, idempotency_key, action_type, actor, producer_plugin,
                lifecycle, outcome, occurred_at, provenance, confidence,
                target_face, summary, authoritative_domain, authoritative_record_id,
                context
            ) VALUES (
                $1, 'k', 'a', 'a', 'p', 'succeeded', 'success', now(),
                'synthesized', 1.0, 'world', 's', 'd', 'r', '{"goal_id": "g"}'::jsonb
            )
            """,
            uuid4(),
        )
        await conn.execute(zm025.REPAIR_SQL)
        got = await conn.fetchval("SELECT context->>'goal_id' FROM action_records")
    assert got == "g"


async def test_subject_key_indexes_exist(pg_pool):
    async with pg_pool.acquire() as conn:
        names = {
            r["indexname"]
            for r in await conn.fetch(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'action_records'"
            )
        }
    assert {f"action_records_{k}_idx" for k in zm025.SUBJECT_KEYS} <= names
