from __future__ import annotations

import re
from collections import Counter
from unittest.mock import AsyncMock, MagicMock

from ze_automation.bootstrap import automation_data_domains
from ze_core.bootstrap import engine_data_domains
from ze_memory.feedback_records.data_domain import feedback_data_domains
from ze_personal.plugin import PersonalPlugin
from ze_proactive.data_domain import interruption_data_domains
from ze_worldstate.bootstrap import worldstate_data_domains

_FROM = re.compile(r"FROM\s+(\w+)")


def _recording_pool() -> tuple[MagicMock, list[str]]:
    statements: list[str] = []

    async def _record(sql: str, *args) -> list:
        statements.append(sql)
        return []

    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=_record)
    conn.execute = AsyncMock(side_effect=_record)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=ctx)
    return pool, statements


def _container_domains(pool):
    return (
        engine_data_domains(pool)
        + automation_data_domains(pool)
        + worldstate_data_domains(pool)
        + feedback_data_domains(pool)
        + interruption_data_domains(pool)
        + PersonalPlugin.data_domains(PersonalPlugin.__new__(PersonalPlugin))
    )


async def _tables(call, domains, pool, statements) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    for domain in domains:
        statements.clear()
        await call(domain)(pool)
        seen.extend((domain.name, _FROM.search(sql).group(1)) for sql in statements)
    return seen


async def test_each_table_is_exported_by_one_domain():
    pool, statements = _recording_pool()
    domains = _container_domains(pool)

    exported = await _tables(lambda d: d.export, domains, pool, statements)

    counts = Counter(table for _, table in exported)
    duplicated = {
        table: [name for name, t in exported if t == table]
        for table, n in counts.items()
        if n > 1
    }
    assert duplicated == {}
    assert {"goals", "workflows"} <= set(counts)


async def test_domain_names_are_unique():
    pool, _ = _recording_pool()
    names = Counter(d.name for d in _container_domains(pool))
    assert [name for name, n in names.items() if n > 1] == []


async def test_goals_are_deleted_after_open_loops():
    pool, statements = _recording_pool()
    domains = _container_domains(pool)
    orders: dict[str, list[int]] = {}
    for domain in domains:
        statements.clear()
        await domain.delete(pool)
        for sql in statements:
            orders.setdefault(_FROM.search(sql).group(1), []).append(
                domain.delete_order
            )

    assert min(orders["goals"]) > max(orders["open_loops"])
