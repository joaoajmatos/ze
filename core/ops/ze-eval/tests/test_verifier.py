import asyncio
from unittest.mock import AsyncMock

from ze_eval.verifier import _check


def _run(check: dict, count: int):
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=count)
    return asyncio.run(_check(conn, check))


def test_exists_and_not_exists_follow_the_row_count():
    base = {"table": "open_loops", "where": {"title__icontains": "x"}}
    assert _run({**base, "expect": "exists"}, 1).passed is True
    assert _run({**base, "expect": "exists"}, 0).passed is False
    assert _run({**base, "expect": "not_exists"}, 0).passed is True


def test_any_passes_whether_or_not_a_row_was_created():
    base = {"table": "open_loops", "where": {"title__icontains": "x"}, "expect": "any"}
    assert _run(base, 0).passed is True
    assert _run(base, 3).passed is True


def test_created_since_run_scopes_the_query_and_cleanup():
    from datetime import UTC, datetime

    from ze_eval.verifier import _cleanup

    since = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    check = {
        "table": "open_loops",
        "where": {"title__icontains": "bank"},
        "created_since_run": True,
    }
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    asyncio.run(_check(conn, check, since))
    sql, *params = conn.fetchval.await_args.args
    assert "created_at >= $2" in sql and params == ["%bank%", since]

    asyncio.run(_cleanup(conn, check, since))
    sql, *params = conn.execute.await_args.args
    assert sql.startswith("DELETE") and "created_at >= $2" in sql and params[-1] == since
