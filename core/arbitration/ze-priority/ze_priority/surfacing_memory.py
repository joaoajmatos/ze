"""What the conversation already raised: inline mentions and resume offers.

The push bar reads this through ``TurnSurfacing.mentioned_inline_within`` so an
interruption does not repeat what the user just saw in chat.
"""

from __future__ import annotations

from typing import Literal, Protocol, Sequence
from uuid import UUID

from ze_agents.db import DBPool

SurfacingKind = Literal["inline", "offer"]

RETENTION_DAYS = 30


class SurfacingMemory(Protocol):
    async def record(
        self, kind: SurfacingKind, source_kind: str, source_ids: Sequence[UUID]
    ) -> None: ...

    async def recorded_within(
        self, kind: SurfacingKind, source_kind: str, source_id: UUID, hours: float
    ) -> bool: ...


class PostgresSurfacingMemory:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def record(
        self, kind: SurfacingKind, source_kind: str, source_ids: Sequence[UUID]
    ) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM surfacing_memory"
                    " WHERE recorded_at < now() - make_interval(days => $1)",
                    RETENTION_DAYS,
                )
                if source_ids:
                    await conn.executemany(
                        "INSERT INTO surfacing_memory (kind, source_kind, source_id)"
                        " VALUES ($1, $2, $3)",
                        [(kind, source_kind, source_id) for source_id in source_ids],
                    )

    async def recorded_within(
        self, kind: SurfacingKind, source_kind: str, source_id: UUID, hours: float
    ) -> bool:
        async with self._pool.acquire() as conn:
            return bool(
                await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM surfacing_memory"
                    " WHERE source_kind = $1 AND source_id = $2 AND kind = $3"
                    " AND recorded_at > now() - make_interval(secs => $4))",
                    source_kind,
                    source_id,
                    kind,
                    float(hours) * 3600.0,
                )
            )
