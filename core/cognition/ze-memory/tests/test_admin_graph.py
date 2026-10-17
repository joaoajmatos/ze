from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.admin import _aliases_from_row, _attrs_from_row, search_entities


def test_aliases_from_row_parses_json_string():
    assert _aliases_from_row('["Marco"]') == ["Marco"]


def test_aliases_from_row_passes_through_list():
    assert _aliases_from_row(["Ana"]) == ["Ana"]


def test_attrs_from_row_parses_json_string():
    assert _attrs_from_row('{"role": "partner"}') == {"role": "partner"}


def test_attrs_from_row_passes_through_dict():
    assert _attrs_from_row({"level": "A2"}) == {"level": "A2"}


def _pool(conn: AsyncMock) -> MagicMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=ctx)
    return pool


def _row(name="Ada", aliases='["A"]'):
    return {
        "id": uuid4(),
        "entity_type": "person",
        "canonical_name": name,
        "aliases": aliases,
        "attrs": "{}",
        "degree": 3,
    }


async def test_search_entities_matches_name_and_alias_ordered_by_degree():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[_row()])

    result = await search_entities(_pool(conn), q="ad", entity_type=None, limit=20)

    sql, *args = conn.fetch.call_args[0]
    assert "e.canonical_name ILIKE $1 ESCAPE" in sql
    assert "jsonb_array_elements_text(e.aliases)" in sql
    assert "ORDER BY degree DESC, e.canonical_name" in sql
    assert args == ["%ad%", None, 20]
    assert result[0]["canonical_name"] == "Ada"
    assert result[0]["aliases"] == ["A"]
    assert result[0]["degree"] == 3


async def test_search_entities_escapes_like_wildcards():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    await search_entities(_pool(conn), q="50%_a\\b", entity_type="project", limit=5)

    args = list(conn.fetch.call_args[0][1:])
    assert args == ["%50\\%\\_a\\\\b%", "project", 5]
