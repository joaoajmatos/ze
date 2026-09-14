from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_plugin.contribution import SourceFunction

from ze_collision.rest import list_collisions


async def test_list_collisions_passes_through_all_filters() -> None:
    store = AsyncMock()
    store.list.return_value = []
    entity_id = uuid4()
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    until = datetime(2026, 2, 1, tzinfo=timezone.utc)

    result = await list_collisions(
        store,
        entity_id=entity_id,
        source_function=SourceFunction.REFLECTION,
        since=since,
        until=until,
        limit=25,
    )

    assert result == []
    store.list.assert_awaited_once_with(
        entity_id=entity_id,
        source_function=SourceFunction.REFLECTION,
        since=since,
        until=until,
        limit=25,
    )


async def test_list_collisions_defaults() -> None:
    store = AsyncMock()
    store.list.return_value = []

    await list_collisions(store)

    store.list.assert_awaited_once_with(
        entity_id=None,
        source_function=None,
        since=None,
        until=None,
        limit=50,
    )
