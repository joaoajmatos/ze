import pytest
from ze_proactive.push_log_store import PushLogStore

pytestmark = pytest.mark.pg


async def test_window_sent_at_returns_claims_inside_window_ascending(pg_pool):
    async with pg_pool.acquire() as conn:
        for key, hours in (("a", 20), ("b", 2), ("c", 10), ("old", 30)):
            await conn.execute(
                "INSERT INTO push_log (event_type, idempotency_key, sent_at) "
                "VALUES ('attention_push', $1, now() - make_interval(hours => $2))",
                key,
                hours,
            )
        await conn.execute(
            "INSERT INTO push_log (event_type, idempotency_key) VALUES ('other', 'x')"
        )

    stamps = await PushLogStore(pg_pool).window_sent_at("attention_push", 24.0)

    assert len(stamps) == 3
    assert stamps == sorted(stamps)
