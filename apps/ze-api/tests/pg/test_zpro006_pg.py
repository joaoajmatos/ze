import asyncpg
import pytest
from ze_api.cli import migrate

pytestmark = pytest.mark.pg


async def test_zpro006_round_trips_with_repeat_claims_of_one_key(pg_dsn):
    sync_url = pg_dsn.replace("postgresql://", "postgresql+psycopg2://", 1)
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("TRUNCATE push_log RESTART IDENTITY")
        for age_days in (10, 0):
            for event_type, key in (("attention_push", "loop:1"), ("acc", "weekly")):
                await conn.execute(
                    "INSERT INTO push_log (event_type, claim_key, discretionary, sent_at) "
                    "VALUES ($1, $2, TRUE, now() - make_interval(days => $3))",
                    event_type,
                    key,
                    age_days,
                )
        await conn.close()

        migrate.downgrade(sync_url, "zpro005")

        conn = await asyncpg.connect(pg_dsn)
        rows = await conn.fetch(
            "SELECT event_type, idempotency_key, sent_at FROM push_log ORDER BY id"
        )
        assert sorted((r["event_type"], r["idempotency_key"]) for r in rows) == [
            ("acc", "weekly"),
            ("attention_push", "loop:1"),
        ]
        assert all(r["sent_at"] is not None for r in rows)
        await conn.close()
    finally:
        migrate.upgrade(sync_url)

    conn = await asyncpg.connect(pg_dsn)
    try:
        # upgrade keeps only keyed attention_push rows; the "acc" row goes
        assert await conn.fetchval("SELECT count(*) FROM push_log") == 1
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'push_log' AND column_name = 'claim_key'"
            )
            == 1
        )
    finally:
        await conn.execute("TRUNCATE push_log RESTART IDENTITY")
        await conn.close()
