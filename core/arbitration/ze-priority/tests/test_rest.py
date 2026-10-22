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
        computed_rank=rank,
        activity_at=datetime.now(UTC),
    )


def _override_for(item: PriorityItem, anchor: PriorityItem):
    from ze_priority.types import PriorityOverride

    return PriorityOverride(
        id=uuid4(),
        source_kind=item.source_kind,
        source_id=item.source_id,
        anchor_source_kind=anchor.source_kind,
        anchor_source_id=anchor.source_id,
        relation="above",
        pinned=True,
        submitted_at=datetime.now(UTC),
        superseded_at=None,
        contribution_domain_id=uuid4(),
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

    result = await get_snapshot(view)

    assert isinstance(result, PrioritySnapshotResult)
    assert result.sources_failed == ("goal", "loop")
    assert [row.source_id for row in result.items] == [item.source_id]


async def test_get_snapshot_no_failed_sources_is_empty_tuple():
    view = _view_with(set(), [_item("Follow up with Maria", 1)])

    result = await get_snapshot(view)

    assert result.sources_failed == ()


async def test_get_snapshot_rows_are_the_views_order_with_its_ranks():
    first = _item("B", 1)
    first.computed_rank = 2
    first.override = _override_for(first, _item("A", 2))
    second = _item("A", 2)
    second.computed_rank = 1
    view = _view_with(set(), [first, second])

    result = await get_snapshot(view)

    assert [row.source_id for row in result.items] == [
        first.source_id,
        second.source_id,
    ]
    top, other = result.items
    assert (top.displayed_rank, top.computed_rank) == (1, 2)
    assert top.overridden_from_computed is True
    assert top.override is first.override
    assert (other.displayed_rank, other.computed_rank) == (2, 1)
    assert other.overridden_from_computed is True
    assert other.override is None


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
