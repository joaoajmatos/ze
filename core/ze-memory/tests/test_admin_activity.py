from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.admin import get_entity_detail, get_memory_activity


def _pool(conn: AsyncMock) -> MagicMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=ctx)
    return pool


async def test_get_entity_detail_returns_fact_created_at():
    entity_id = uuid4()
    created_at = datetime(2026, 7, 2, 14, 3, tzinfo=timezone.utc)
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "id": entity_id,
            "entity_type": "person",
            "canonical_name": "Ada",
            "aliases": [],
            "attrs": {},
            "degree": 0,
        }
    )
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "id": uuid4(),
                    "key": "favorite_color",
                    "value": "teal",
                    "agent": "companion",
                    "created_at": created_at,
                }
            ],
            [],
            [],
        ]
    )

    result = await get_entity_detail(_pool(conn), entity_id)

    assert result is not None
    assert result["facts"][0]["created_at"] == created_at
    fact_sql = conn.fetch.call_args_list[0][0][0]
    assert "f.created_at" in fact_sql


async def test_get_memory_activity_splits_fact_and_episode_counts():
    day = date(2026, 7, 2)
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"day": day, "source": "fact", "count": 3},
            {"day": day, "source": "episode", "count": 2},
        ]
    )

    result = await get_memory_activity(
        _pool(conn),
        datetime(2026, 7, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 3, tzinfo=timezone.utc),
    )

    assert result["days"] == [
        {
            "date": "2026-07-02",
            "fact_count": 3,
            "episode_count": 2,
            "count": 5,
        }
    ]
    assert result["max_count"] == 5
    assert result["days"][0]["fact_count"] + result["days"][0]["episode_count"] == result[
        "days"
    ][0]["count"]
