from datetime import timedelta

import pytest
from ze_proactive.notification_store import NotificationStore

pytestmark = pytest.mark.pg


async def _insert(
    pg_pool, title, *, delivery, push_class, created_ago, delivered_ago=None
):
    async with pg_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO notifications
                (event_type, source, title, body, push_class, urgency, format,
                 actions, delivery, created_at, delivered_at)
            VALUES ('e', 's', $1, 'b', $2, 'normal', 'text', '[]'::jsonb, $3,
                    now() - $4::interval,
                    CASE WHEN $5::interval IS NULL THEN NULL
                         ELSE now() - $5::interval END)
            """,
            title,
            push_class,
            delivery,
            created_ago,
            delivered_ago,
        )


async def test_filters_and_since_use_delivered_at_when_present(pg_pool):
    hour = timedelta(hours=1)
    # Held before the user left, released after: news.
    await _insert(
        pg_pool,
        "released-late",
        delivery="released",
        push_class="discretionary",
        created_ago=10 * hour,
        delivered_ago=1 * hour,
    )
    # Delivered before the user left: not news.
    await _insert(
        pg_pool,
        "delivered-early",
        delivery="delivered",
        push_class="discretionary",
        created_ago=10 * hour,
        delivered_ago=9 * hour,
    )
    # Suppressed after the user left; never delivered.
    await _insert(
        pg_pool,
        "suppressed",
        delivery="suppressed",
        push_class="discretionary",
        created_ago=2 * hour,
    )
    await _insert(
        pg_pool,
        "acc",
        delivery="delivered",
        push_class="accountability",
        created_ago=1 * hour,
        delivered_ago=1 * hour,
    )

    store = NotificationStore(pg_pool)
    from datetime import datetime, timezone

    since = datetime.now(timezone.utc) - 5 * hour

    items, _ = await store.list_page(since=since)
    assert {i.title for i in items} == {"released-late", "suppressed", "acc"}

    items, _ = await store.list_page(
        since=since, delivery=["released", "suppressed"], push_class="discretionary"
    )
    assert {i.title for i in items} == {"released-late", "suppressed"}
    assert next(i for i in items if i.title == "released-late").delivered_at is not None
