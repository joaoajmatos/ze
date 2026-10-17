"""Every `setup:` kind inserts and deletes against the real, migrated schema."""

import pytest
from ze_eval.fixtures import KINDS, Fixtures

pytestmark = pytest.mark.pg

PARENTS = {"goal_gate": "goal", "workflow_execution": "workflow"}


@pytest.mark.parametrize("kind", sorted(KINDS))
async def test_each_kind_round_trips(pg_pool, pg_dsn, kind):
    items = []
    if kind in PARENTS:
        items.append({"kind": PARENTS[kind], "name": "parent"})
    items.append(
        {
            "kind": kind,
            "name": "row",
            **({"parent": "parent"} if kind in PARENTS else {}),
        }
    )
    fixtures = await Fixtures.create(items, db_url=pg_dsn)
    try:
        assert fixtures.bindings["row"]["id"]
        table = KINDS[kind].table
        async with pg_pool.acquire() as conn:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
        assert count >= 1
    finally:
        await fixtures.delete()
    async with pg_pool.acquire() as conn:
        for item in items:
            left = await conn.fetchval(
                f"SELECT COUNT(*) FROM {KINDS[item['kind']].table}"
            )
            assert left == 0, item["kind"]


async def test_a_failed_setup_leaves_nothing_behind(pg_pool, pg_dsn):
    from ze_eval.fixtures import FixtureError

    with pytest.raises(FixtureError):
        await Fixtures.create(
            [
                {"kind": "goal", "name": "g"},
                {
                    "kind": "goal",
                    "name": "bad",
                    "fields": {"status": None, "title": None},
                },
            ],
            db_url=pg_dsn,
        )
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT COUNT(*) FROM goals") == 0
