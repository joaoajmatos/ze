from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


from ze_memory import admin as memory_admin


def make_pool(fetch_return=None):
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_return if fetch_return is not None else [])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


async def test_get_profile_returns_facets():
    now = datetime(2026, 5, 20, 2, 0, 0, tzinfo=timezone.utc)
    rows = [
        {
            "key": "preferences",
            "value": "Likes brevity.",
            "stability": "stable",
            "confidence": 0.9,
            "updated_at": now,
        },
        {
            "key": "topics",
            "value": "AI.",
            "stability": "dynamic",
            "confidence": 0.8,
            "updated_at": now,
        },
    ]
    pool, conn = make_pool(fetch_return=rows)
    result = await memory_admin.get_profile(pool)
    assert result is not None
    assert result["facets"][0]["key"] == "preferences"
    assert result["facets"][0]["value"] == "Likes brevity."
    assert result["updated_at"] == now
    sql = conn.fetch.call_args_list[0][0][0]
    assert "memory_profile_facets" in sql
    assert "user_profile" not in sql


async def test_get_profile_none_when_no_facets():
    pool, _ = make_pool(fetch_return=[])
    assert await memory_admin.get_profile(pool) is None
