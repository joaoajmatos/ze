import pytest
from ze_memory.admin import get_entity_detail, search_entities

pytestmark = pytest.mark.pg


async def _entity(conn, name, etype="person", aliases="[]"):
    return await conn.fetchval(
        "INSERT INTO memory_entities (entity_type, canonical_name, aliases) "
        "VALUES ($1, $2, $3::jsonb) RETURNING id",
        etype,
        name,
        aliases,
    )


async def _edge(conn, source, target, predicate="works_with"):
    await conn.execute(
        "INSERT INTO memory_relationships "
        "(source_id, source_type, predicate, target_id, target_type) "
        "VALUES ($1, 'entity', $2, $3, 'entity')",
        source,
        predicate,
        target,
    )


async def test_search_by_alias_partial_name_and_type(pg_pool):
    async with pg_pool.acquire() as conn:
        ada = await _entity(conn, "Ada Lovelace", aliases='["Countess"]')
        await _entity(conn, "Acme", "organization")

    by_alias = await search_entities(pg_pool, q="countess", entity_type=None, limit=10)
    by_name = await search_entities(pg_pool, q="lovel", entity_type=None, limit=10)
    by_type = await search_entities(pg_pool, q="a", entity_type="organization", limit=10)
    none = await search_entities(pg_pool, q="zzz", entity_type=None, limit=10)

    assert [r["id"] for r in by_alias] == [ada]
    assert [r["id"] for r in by_name] == [ada]
    assert [r["canonical_name"] for r in by_type] == ["Acme"]
    assert none == []


async def test_search_treats_percent_literally(pg_pool):
    async with pg_pool.acquire() as conn:
        await _entity(conn, "100% Pure")
        await _entity(conn, "Other")

    result = await search_entities(pg_pool, q="%", entity_type=None, limit=10)

    assert [r["canonical_name"] for r in result] == ["100% Pure"]


async def test_entity_detail_caps_neighbours_in_degree_then_name_order(pg_pool):
    async with pg_pool.acquire() as conn:
        centre = await _entity(conn, "Centre")
        busy = None
        for i in range(25):
            n = await _entity(conn, f"N{i:02d}")
            await _edge(conn, centre, n)
            if i == 24:
                busy = n
        extra = await _entity(conn, "Extra")
        await _edge(conn, busy, extra)

    detail = await get_entity_detail(pg_pool, centre)

    names = [n["canonical_name"] for n in detail["neighbours"]]
    assert len(names) == 20
    assert detail["neighbour_total"] == 25
    assert names[0] == "N24"
    assert names[1:] == [f"N{i:02d}" for i in range(19)]
