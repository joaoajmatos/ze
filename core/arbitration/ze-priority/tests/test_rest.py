"""Unit tests for `ze_priority.rest` (Phase 170 US4)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind, Confidence, DecayProfile

from ze_priority.rest import get_snapshot
from ze_priority.types import PriorityItem, PriorityRanking, PrioritySnapshotResult

UTC = timezone.utc


def _item(title: str, rank: int) -> PriorityItem:
    return PriorityItem(
        source_kind="loop",
        claim_kind=ClaimKind.PRIORITY,
        source_id=uuid4(),
        title=title,
        signal=None,
        priority=Confidence(value=1.0, decay_profile=DecayProfile.TIME_LINEAR),
        rank=rank,
        activity_at=datetime.now(UTC),
    )


def _view_with(sources_failed: set, items: list[PriorityItem]) -> AsyncMock:
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=items,
        sources_succeeded={"loop", "goal", "hypothesis"} - sources_failed,
        sources_failed=sources_failed,
        generated_at=datetime.now(UTC),
    )
    return view


async def test_get_snapshot_reports_failed_sources_sorted():
    item = _item("Follow up with Maria", 1)
    view = _view_with({"goal", "loop"}, [item])
    override_store = AsyncMock()
    override_store.get_active.return_value = []

    result = await get_snapshot(view, override_store)

    assert isinstance(result, PrioritySnapshotResult)
    assert result.sources_failed == ("goal", "loop")
    assert [row.source_id for row in result.items] == [item.source_id]


async def test_get_snapshot_no_failed_sources_is_empty_tuple():
    view = _view_with(set(), [_item("Follow up with Maria", 1)])
    override_store = AsyncMock()
    override_store.get_active.return_value = []

    result = await get_snapshot(view, override_store)

    assert result.sources_failed == ()
