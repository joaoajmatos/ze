from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_plugin.contribution import SourceFunction, TargetFace

from ze_collision.store import PostgresCollisionLogStore
from ze_collision.types import CollisionLogEntry


def _entry(**overrides) -> CollisionLogEntry:
    defaults = dict(
        id=None,
        contribution_a_domain_id=uuid4(),
        contribution_a_producer_kind="open_loop",
        contribution_a_source_function=SourceFunction.PERCEPTION,
        contribution_a_claim_kind=ClaimKind.FACT,
        contribution_b_domain_id=uuid4(),
        contribution_b_producer_kind="hypothesis",
        contribution_b_source_function=SourceFunction.REFLECTION,
        contribution_b_claim_kind=ClaimKind.INFERENCE,
        matched_entity_id=uuid4(),
        matched_target_face=TargetFace.WORLD,
        conflict_summary="conflict",
        created_at=None,
    )
    defaults.update(overrides)
    return CollisionLogEntry(**defaults)


def _row_from_entry(entry: CollisionLogEntry, **overrides) -> dict:
    row = {
        "id": uuid4(),
        "contribution_a_domain_id": entry.contribution_a_domain_id,
        "contribution_a_producer_kind": entry.contribution_a_producer_kind,
        "contribution_a_source_function": entry.contribution_a_source_function.value,
        "contribution_a_claim_kind": entry.contribution_a_claim_kind.value,
        "contribution_b_domain_id": entry.contribution_b_domain_id,
        "contribution_b_producer_kind": entry.contribution_b_producer_kind,
        "contribution_b_source_function": entry.contribution_b_source_function.value,
        "contribution_b_claim_kind": entry.contribution_b_claim_kind.value,
        "matched_entity_id": entry.matched_entity_id,
        "matched_target_face": entry.matched_target_face.value,
        "conflict_summary": entry.conflict_summary,
        "created_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


def _pool_with(fetchrow_result=None, fetch_result=None):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    conn.fetch = AsyncMock(return_value=fetch_result or [])

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


async def test_log_inserts_and_returns_populated_entry() -> None:
    entry = _entry()
    row = _row_from_entry(entry)
    pool, conn = _pool_with(fetchrow_result=row)
    store = PostgresCollisionLogStore(pool=pool)

    result = await store.log(entry)

    assert conn.fetchrow.await_count == 1
    assert result.id == row["id"]
    assert result.created_at == row["created_at"]
    assert result.contribution_a_source_function == SourceFunction.PERCEPTION
    assert result.contribution_b_claim_kind == ClaimKind.INFERENCE


async def test_list_with_no_filters_uses_no_where_clause() -> None:
    pool, conn = _pool_with(fetch_result=[])
    store = PostgresCollisionLogStore(pool=pool)

    result = await store.list()

    assert result == []
    query = conn.fetch.await_args.args[0]
    assert "WHERE" not in query
    assert "LIMIT $1" in query


async def test_list_filters_by_entity_id() -> None:
    entity_id = uuid4()
    entry = _entry(matched_entity_id=entity_id)
    row = _row_from_entry(entry)
    pool, conn = _pool_with(fetch_result=[row])
    store = PostgresCollisionLogStore(pool=pool)

    result = await store.list(entity_id=entity_id)

    assert len(result) == 1
    query, *params = conn.fetch.await_args.args
    assert "matched_entity_id = $1" in query
    assert params[0] == entity_id


async def test_list_filters_by_source_function_either_side() -> None:
    pool, conn = _pool_with(fetch_result=[])
    store = PostgresCollisionLogStore(pool=pool)

    await store.list(source_function=SourceFunction.REFLECTION)

    query, *params = conn.fetch.await_args.args
    assert "contribution_a_source_function = $1" in query
    assert "contribution_b_source_function = $1" in query
    assert params[0] == SourceFunction.REFLECTION.value


async def test_list_combines_date_range_filters() -> None:
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    until = datetime(2026, 2, 1, tzinfo=timezone.utc)
    pool, conn = _pool_with(fetch_result=[])
    store = PostgresCollisionLogStore(pool=pool)

    await store.list(since=since, until=until, limit=10)

    query, *params = conn.fetch.await_args.args
    assert "created_at >= $1" in query
    assert "created_at <= $2" in query
    assert "LIMIT $3" in query
    assert params == [since, until, 10]
