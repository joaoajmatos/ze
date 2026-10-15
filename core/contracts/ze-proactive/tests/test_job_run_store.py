from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from ze_proactive.job_run_store import JobRunStore


def _pool(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    return pool


async def test_record_start_upserts_running():
    conn = AsyncMock()
    await JobRunStore(_pool(conn)).record_start("briefing")
    sql = conn.execute.call_args.args[0]
    assert "ON CONFLICT (job_id) DO UPDATE" in sql and "'running'" in sql
    assert conn.execute.call_args.args[1] == "briefing"


async def test_record_finish_sets_status():
    conn = AsyncMock()
    await JobRunStore(_pool(conn)).record_finish("briefing", "error")
    sql, job_id, status = conn.execute.call_args.args
    assert "last_finished_at" in sql and (job_id, status) == ("briefing", "error")


async def test_get_all_maps_rows():
    now = datetime(2026, 6, 15, tzinfo=timezone.utc)
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "job_id": "a",
                "last_started_at": now,
                "last_finished_at": None,
                "last_status": "running",
            }
        ]
    )
    runs = await JobRunStore(_pool(conn)).get_all()
    assert runs["a"].last_started_at == now and runs["a"].last_status == "running"


async def test_store_errors_are_swallowed():
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=RuntimeError("down"))
    store = JobRunStore(pool)
    await store.record_start("a")
    await store.record_finish("a", "ok")
    assert await store.get_all() == {}
