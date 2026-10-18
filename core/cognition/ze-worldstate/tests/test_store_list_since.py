from __future__ import annotations

from datetime import datetime, timezone

from ze_worldstate.store import PostgresLoopStore

from tests.conftest import make_pool


def _sql(conn) -> str:
    return " ".join(conn.fetch.await_args.args[0].split())


async def test_since_adds_updated_at_bound_and_the_state_set():
    pool, conn = make_pool()
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)

    await PostgresLoopStore(pool=pool).list(states=["closed", "dropped"], since=since)

    assert conn.fetch.await_args.args[1:] == (["closed", "dropped"], since)
    sql = _sql(conn)
    assert "state = ANY($1)" in sql
    assert "updated_at > $2" in sql


async def test_since_alone_filters_without_a_state_clause():
    pool, conn = make_pool()
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)

    await PostgresLoopStore(pool=pool).list(since=since)

    assert conn.fetch.await_args.args[1:] == (since,)
    sql = _sql(conn)
    assert "state" not in sql.split("ORDER BY")[0].replace("SELECT * FROM", "")
    assert "updated_at > $1" in sql


async def test_without_since_the_sql_is_unchanged():
    pool, conn = make_pool()

    await PostgresLoopStore(pool=pool).list(["suspected", "active"])

    assert conn.fetch.await_args.args == (
        "SELECT * FROM open_loops WHERE state = ANY($1) ORDER BY created_at DESC",
        ["suspected", "active"],
    )


async def test_no_arguments_lists_everything():
    pool, conn = make_pool()

    await PostgresLoopStore(pool=pool).list()

    assert conn.fetch.await_args.args == (
        "SELECT * FROM open_loops ORDER BY created_at DESC",
    )
