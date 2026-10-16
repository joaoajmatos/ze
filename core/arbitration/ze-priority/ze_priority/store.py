from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from ze_logging import get_logger
from ze_agents.db import DBPool

from ze_priority.errors import (
    PriorityOverrideNotFoundError,
    StalePriorityRestoreError,
)
from ze_priority.types import PriorityOverride

log = get_logger(__name__)

UTC = timezone.utc


def _override_from_row(row) -> PriorityOverride:
    return PriorityOverride(
        id=row["id"],
        source_kind=row["source_kind"],
        source_id=row["source_id"],
        anchor_source_kind=row["anchor_source_kind"],
        anchor_source_id=row["anchor_source_id"],
        relation=row["relation"],
        pinned=row["pinned"],
        submitted_at=row["submitted_at"],
        superseded_at=row["superseded_at"],
        contribution_domain_id=row["contribution_domain_id"],
    )


class PriorityOverrideStore(Protocol):
    async def create(
        self, override: PriorityOverride
    ) -> tuple[PriorityOverride, UUID | None]: ...

    async def restore(
        self, override_id: UUID, prior_override_id: UUID | None
    ) -> PriorityOverride | None: ...

    async def get(self, override_id: UUID) -> PriorityOverride | None: ...

    async def get_active(self) -> list[PriorityOverride]: ...

    async def unpin(self, override_id: UUID) -> PriorityOverride: ...


class PostgresPriorityOverrideStore:
    def __init__(self, pool: DBPool) -> None:
        self._pool = pool

    async def create(
        self, override: PriorityOverride
    ) -> tuple[PriorityOverride, UUID | None]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                superseded = await conn.fetchrow(
                    """
                    UPDATE priority_overrides
                    SET superseded_at = $1
                    WHERE source_kind = $2 AND source_id = $3 AND superseded_at IS NULL
                    RETURNING id
                    """,
                    override.submitted_at,
                    override.source_kind,
                    override.source_id,
                )
                row = await conn.fetchrow(
                    """
                    INSERT INTO priority_overrides (
                        id, source_kind, source_id, anchor_source_kind,
                        anchor_source_id, relation, pinned, submitted_at,
                        superseded_at, contribution_domain_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING *
                    """,
                    override.id,
                    override.source_kind,
                    override.source_id,
                    override.anchor_source_kind,
                    override.anchor_source_id,
                    override.relation,
                    override.pinned,
                    override.submitted_at,
                    override.superseded_at,
                    override.contribution_domain_id,
                )
        log.info(
            "priority_override_created",
            source_kind=override.source_kind,
            source_id=str(override.source_id),
            pinned=override.pinned,
        )
        assert row is not None
        return _override_from_row(row), superseded["id"] if superseded else None

    async def restore(
        self, override_id: UUID, prior_override_id: UUID | None
    ) -> PriorityOverride | None:
        reinstated = None
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT * FROM priority_overrides"
                    " WHERE id = $1 AND superseded_at IS NULL FOR UPDATE",
                    override_id,
                )
                if current is None:
                    raise StalePriorityRestoreError(
                        f"priority override {override_id} changed after the "
                        "reprioritization"
                    )
                await conn.execute(
                    "UPDATE priority_overrides SET superseded_at = $2 WHERE id = $1",
                    override_id,
                    datetime.now(UTC),
                )
                prior = (
                    await conn.fetchrow(
                        "SELECT * FROM priority_overrides WHERE id = $1 FOR UPDATE",
                        prior_override_id,
                    )
                    if prior_override_id is not None
                    else None
                )
                if (
                    prior is not None
                    and prior["superseded_at"] == current["submitted_at"]
                ):
                    reinstated = await conn.fetchrow(
                        """
                        INSERT INTO priority_overrides (
                            id, source_kind, source_id, anchor_source_kind,
                            anchor_source_id, relation, pinned, submitted_at,
                            superseded_at, contribution_domain_id
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NULL, $9)
                        RETURNING *
                        """,
                        uuid4(),
                        prior["source_kind"],
                        prior["source_id"],
                        prior["anchor_source_kind"],
                        prior["anchor_source_id"],
                        prior["relation"],
                        prior["pinned"],
                        prior["submitted_at"],
                        prior["contribution_domain_id"],
                    )
        log.info(
            "priority_override_restored",
            override_id=str(override_id),
            reinstated=reinstated is not None,
        )
        return _override_from_row(reinstated) if reinstated else None

    async def get(self, override_id: UUID) -> PriorityOverride | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM priority_overrides WHERE id = $1", override_id
            )
        return _override_from_row(row) if row else None

    async def get_active(self) -> list[PriorityOverride]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM priority_overrides WHERE superseded_at IS NULL"
                " ORDER BY submitted_at ASC"
            )
        return [_override_from_row(row) for row in rows]

    async def unpin(self, override_id: UUID) -> PriorityOverride:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE priority_overrides
                SET pinned = false, submitted_at = $2
                WHERE id = $1 AND superseded_at IS NULL
                RETURNING *
                """,
                override_id,
                datetime.now(UTC),
            )
        if row is None:
            raise PriorityOverrideNotFoundError(
                f"no active priority override with id {override_id}"
            )
        return _override_from_row(row)
