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


async def test_submit_override_unpacks_service_tuple():
    from unittest.mock import patch

    from ze_priority.rest import submit_override
    from ze_priority.types import PriorityOverride, PriorityOverrideRequest

    item = _item("Follow up with Maria", 1)
    anchor = _item("Other", 2)
    view = _view_with(set(), [item, anchor])
    override_store = AsyncMock()
    override_store.get_active.return_value = []
    override = PriorityOverride(
        id=uuid4(),
        source_kind="loop",
        source_id=item.source_id,
        anchor_source_kind="loop",
        anchor_source_id=anchor.source_id,
        relation="below",
        pinned=False,
        submitted_at=datetime.now(UTC),
        superseded_at=None,
        contribution_domain_id=uuid4(),
    )
    request = PriorityOverrideRequest(
        source_kind="loop",
        source_id=item.source_id,
        anchor_source_kind="loop",
        anchor_source_id=anchor.source_id,
        relation="below",
        pinned=False,
    )
    with patch(
        "ze_priority.rest.submit_reprioritization",
        AsyncMock(return_value=(override, uuid4())),
    ):
        row = await submit_override(
            request, priority_view=view, override_store=override_store
        )

    assert row.source_id == item.source_id
