import pytest
from ze_calendar.reminders.store import ReminderStore

pytestmark = pytest.mark.pg


async def test_list_by_status_real_sql(pg_pool):
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM user_reminders")
        for label, fire, sent_ago in (
            ("future", "now() + interval '2 hours'", None),
            ("missed", "now() - interval '3 hours'", None),
            ("done-old", "now() - interval '9 hours'", "8 hours"),
            ("done-new", "now() - interval '5 hours'", "1 hour"),
        ):
            await conn.execute(
                f"INSERT INTO user_reminders (label, fire_at, sent, sent_at) "
                f"VALUES ($1, {fire}, $2, "
                + (f"now() - interval '{sent_ago}'" if sent_ago else "NULL")
                + ")",
                label,
                sent_ago is not None,
            )

    store = ReminderStore(pg_pool)

    async def labels(status):
        return [(r.label, due) for r, due in await store.list_by_status(status, 10)]

    assert await labels("upcoming") == [("future", False)]
    assert await labels("overdue") == [("missed", True)]
    assert await labels("fired") == [("done-new", True), ("done-old", True)]
    assert [name for name, _ in await labels("all")] == [
        "future", "missed", "done-new", "done-old"
    ]
