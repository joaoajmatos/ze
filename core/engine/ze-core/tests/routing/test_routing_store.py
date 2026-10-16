"""PostgresRoutingStore.write_log — the log row no longer carries the route-time tier."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from ze_core.routing.store import PostgresRoutingStore
from ze_core.routing.types import RoutingEnvelope, SubTask


def _pool():
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


def _envelope() -> RoutingEnvelope:
    return RoutingEnvelope(
        primary_agent="research",
        confidence=0.8,
        score_gap=0.2,
        routing_method="embedding",
        is_compound=False,
        subtasks=[SubTask(agent="research", intent="read", prompt="p", model="m")],
        requires_synthesis=False,
        raw_scores={"research": 0.8},
    )


async def test_write_log_inserts_neither_dropped_column():
    pool, conn = _pool()
    await PostgresRoutingStore(pool).write_log("s1", "hello", _envelope())

    sql, *params = conn.execute.call_args[0]
    assert "complexity" not in sql
    assert "model_selected" not in sql
    assert params == [
        "s1",
        "hello",
        "embedding",
        "research",
        0.8,
        0.2,
        False,
        json.dumps({"research": 0.8}),
    ]


async def test_write_log_failure_is_swallowed():
    pool, conn = _pool()
    conn.execute.side_effect = RuntimeError("db down")
    await PostgresRoutingStore(pool).write_log("s1", "hello", _envelope())
