from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ze_plugin.contribution import SourceFunction

from ze_collision.store import CollisionLogStore
from ze_collision.types import CollisionLogEntry


async def list_collisions(
    store: CollisionLogStore,
    *,
    entity_id: UUID | None = None,
    source_function: SourceFunction | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
) -> list[CollisionLogEntry]:
    return await store.list(
        entity_id=entity_id,
        source_function=source_function,
        since=since,
        until=until,
        limit=limit,
    )
