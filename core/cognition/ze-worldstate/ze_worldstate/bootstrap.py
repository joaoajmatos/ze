from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import asyncpg

from ze_data.domain import DataDomain
from ze_data.portability.assembler import bulk_insert
from ze_logging import get_logger
from ze_memory.entity_anchor import match_entities_in_query
from ze_memory.graph.store import GraphStore, PostgresGraphStore

from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.jobs.stale_suspicion import (
    DEFAULT_STALE_WINDOW_DAYS,
    StaleSuspicionJob,
)
from ze_worldstate.store import LoopStore, PostgresLoopStore
from ze_worldstate.surfacing import LoopSurfacer

log = get_logger(__name__)


@dataclass
class WorldstateStack:
    loop_store: PostgresLoopStore
    graph_store: GraphStore
    entity_resolver: Any
    pool: Any
    deps: dict[type, Any] = field(default_factory=dict)


def build_worldstate_stack(shared: Any, settings: Any) -> WorldstateStack:
    pool = shared.pool

    loop_store = PostgresLoopStore(pool=pool)
    graph_store = PostgresGraphStore(pool)

    async def entity_resolver(text: str) -> list:
        matches = await match_entities_in_query(text, pool)
        return [m.entity.id for m in matches if m.entity.id is not None]

    deps: dict[type, Any] = {
        LoopStore: loop_store,
        PostgresLoopStore: loop_store,
    }

    return WorldstateStack(
        loop_store=loop_store,
        graph_store=graph_store,
        entity_resolver=entity_resolver,
        pool=pool,
        deps=deps,
    )


def build_loop_surfacer(
    stack: WorldstateStack,
    push_log: Any,
    relevance_model: Any = None,
    embedder: Any = None,
    notifier: Any = None,
) -> LoopSurfacer:
    """Constructed in `ze_api/container.py` once `push_log_store` (and, for the
    push path, the correlation stack's `RelevanceModel`) exist — both are built
    after `build_worldstate_stack` runs."""
    return LoopSurfacer(
        loop_store=stack.loop_store,
        graph_store=stack.graph_store,
        push_log=push_log,
        pool=stack.pool,
        relevance_model=relevance_model,
        embedder=embedder,
        notifier=notifier,
    )


def register_proactive_jobs(
    scheduler: Any,
    settings: Any,
    stack: WorldstateStack,
) -> None:
    cfg = getattr(settings, "config", None) or {}
    worldstate_cfg = cfg.get("worldstate", {}) if isinstance(cfg, dict) else {}
    stale_cfg = worldstate_cfg.get("stale_suspicion", {})
    if stale_cfg.get("enabled", True):
        window_days = int(stale_cfg.get("window_days", DEFAULT_STALE_WINDOW_DAYS))
        job = StaleSuspicionJob(loop_store=stack.loop_store, window_days=window_days)
        scheduler.register(job, cron=stale_cfg.get("cron", "0 4 * * *"))
        log.info("stale_suspicion_job_scheduled", window_days=window_days)

    drift_cfg = worldstate_cfg.get("drift", {})
    if drift_cfg.get("enabled", True):
        drift_job = DriftSweepJob(loop_store=stack.loop_store)
        scheduler.register(drift_job, cron=drift_cfg.get("cron", "0 5 * * *"))
        log.info("drift_sweep_job_scheduled")


def worldstate_data_domains(pool: asyncpg.Pool) -> list[DataDomain]:
    def _export(tbl: str):
        async def _fn(p) -> list[dict]:
            async with pool.acquire() as conn:
                rows = await conn.fetch(f"SELECT * FROM {tbl}")
                return [dict(r) for r in rows]

        return _fn

    def _delete(tbl: str):
        async def _fn(p) -> None:
            async with pool.acquire() as conn:
                await conn.execute(f"DELETE FROM {tbl}")

        return _fn

    def _import(tbl: str):
        async def _fn(conn, rows: list[dict]) -> int:
            return await bulk_insert(conn, tbl, rows)

        return _fn

    def _count(tbl: str):
        async def _fn(p) -> int:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(f"SELECT COUNT(*) AS n FROM {tbl}")
                return row["n"]

        return _fn

    def _size(tbl: str):
        async def _fn(p) -> int:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT pg_total_relation_size($1::regclass) AS n", tbl
                )
                return row["n"]

        return _fn

    return [
        DataDomain(
            "worldstate.open_loops",
            _export("open_loops"),
            _delete("open_loops"),
            delete_order=10,
            importer=_import("open_loops"),
            count=_count("open_loops"),
            size_bytes=_size("open_loops"),
        )
    ]
