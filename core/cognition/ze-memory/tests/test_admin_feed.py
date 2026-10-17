from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.admin import get_entity_detail, get_memory_feed


def _pool(conn: AsyncMock) -> MagicMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=ctx)
    return pool


NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


async def test_feed_selects_claim_kind_for_facts_and_null_for_episodes():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total_facts": 1, "total_episodes": 1})
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "type": "fact",
                "key": "works_at",
                "value": "Acme",
                "confidence": 0.9,
                "reviewed": False,
                "contradicted": False,
                "provenance": "user_stated",
                "claim_kind": "identity",
                "summary": None,
                "prompt_snippet": None,
                "agent": "companion",
                "created_at": NOW,
            }
        ]
    )

    result = await get_memory_feed(_pool(conn), limit=50)

    assert result["items"][0]["claim_kind"] == "identity"
    sql = conn.fetch.call_args[0][0]
    assert "claim_kind" in sql
    assert "NULL::TEXT AS claim_kind" in sql


def _detail_conn(*, fact_rows, neighbour_rows, total):
    entity_id = uuid4()
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
    conn.fetchval = AsyncMock(return_value=total)
    conn.fetch = AsyncMock(side_effect=[fact_rows, [], neighbour_rows, []])
    return conn, entity_id


async def test_entity_detail_facts_carry_claim_fields():
    row = {
        "id": uuid4(),
        "key": "favorite_color",
        "value": "teal",
        "agent": "companion",
        "created_at": NOW,
        "claim_kind": "fact",
        "confidence": 0.8,
        "reviewed": True,
        "contradicted": False,
        "provenance": "user_stated",
    }
    conn, entity_id = _detail_conn(fact_rows=[row], neighbour_rows=[], total=0)

    result = await get_entity_detail(_pool(conn), entity_id)

    fact = result["facts"][0]
    assert fact["claim_kind"] == "fact"
    assert fact["confidence"] == 0.8
    assert fact["reviewed"] is True
    assert fact["contradicted"] is False
    assert fact["provenance"] == "user_stated"
    fact_sql = conn.fetch.call_args_list[0][0][0]
    for col in ("claim_kind", "f.confidence", "f.reviewed", "f.contradicted", "f.provenance"):
        assert col in fact_sql


async def test_entity_detail_orders_neighbours_and_returns_total():
    conn, entity_id = _detail_conn(fact_rows=[], neighbour_rows=[], total=25)

    result = await get_entity_detail(_pool(conn), entity_id)

    assert result["neighbour_total"] == 25
    neighbour_sql = conn.fetch.call_args_list[2][0][0]
    assert "ORDER BY degree DESC, e.canonical_name" in neighbour_sql
    assert "LIMIT 20" in neighbour_sql
    assert "count" in conn.fetchval.call_args[0][0].lower()
