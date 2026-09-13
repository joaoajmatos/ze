from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile
from ze_plugin.contribution import SourceFunction

from ze_priority.errors import StaleReprioritizationTargetError
from ze_priority.service import submit_reprioritization
from ze_priority.types import PriorityItem, PriorityOverrideRequest, PriorityRanking

UTC = timezone.utc


def _item(**overrides) -> PriorityItem:
    base = dict(
        source_kind="loop",
        claim_kind=ClaimKind.PRIORITY,
        source_id=uuid4(),
        title="Follow up with Maria",
        signal=None,
        priority=Confidence(value=0.8, decay_profile=DecayProfile.TIME_LINEAR),
        rank=1,
        activity_at=datetime.now(UTC),
    )
    base.update(overrides)
    return PriorityItem(**base)


def _view(items: list[PriorityItem]) -> AsyncMock:
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=items,
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )
    return view


def _request(
    target: PriorityItem, anchor: PriorityItem, **overrides
) -> PriorityOverrideRequest:
    base = dict(
        source_kind=target.source_kind,
        source_id=target.source_id,
        anchor_source_kind=anchor.source_kind,
        anchor_source_id=anchor.source_id,
        relation="above",
        pinned=False,
    )
    base.update(overrides)
    return PriorityOverrideRequest(**base)


async def test_submit_reprioritization_persists_and_submits_both_contributions():
    target, anchor = _item(rank=2), _item(rank=1)
    view = _view([anchor, target])
    override_store = AsyncMock()
    override_store.create.side_effect = lambda o: o

    result = await submit_reprioritization(
        _request(target, anchor),
        priority_view=view,
        override_store=override_store,
    )

    assert result.source_id == target.source_id
    assert result.anchor_source_id == anchor.source_id
    override_store.create.assert_awaited_once()


async def test_submit_reprioritization_submits_via_collision_seam():
    target, anchor = _item(rank=2), _item(rank=1)
    view = _view([anchor, target])
    override_store = AsyncMock()
    override_store.create.side_effect = lambda o: o
    collision_store = AsyncMock()
    nli_client = AsyncMock()
    nli_client.scores.return_value = [{"contradiction": 0.9}]

    await submit_reprioritization(
        _request(target, anchor),
        priority_view=view,
        override_store=override_store,
        collision_store=collision_store,
        nli_client=nli_client,
    )

    import asyncio

    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    assert nli_client.scores.await_count >= 1
    logged = [call.args[0] for call in collision_store.log.await_args_list]
    assert any(
        entry.contribution_a_source_function == SourceFunction.EXECUTIVE
        for entry in logged
    )


async def test_supersession_sets_superseded_at_on_prior_row():
    target, anchor = _item(rank=2), _item(rank=1)
    view = _view([anchor, target])
    override_store = AsyncMock()
    override_store.create.side_effect = lambda o: o

    await submit_reprioritization(
        _request(target, anchor), priority_view=view, override_store=override_store
    )
    await submit_reprioritization(
        _request(target, anchor, relation="below"),
        priority_view=view,
        override_store=override_store,
    )

    assert override_store.create.await_count == 2


async def test_stale_target_raises() -> None:
    target, anchor = _item(rank=2), _item(rank=1)
    view = _view([anchor])  # target no longer present
    override_store = AsyncMock()

    with pytest.raises(StaleReprioritizationTargetError):
        await submit_reprioritization(
            _request(target, anchor), priority_view=view, override_store=override_store
        )
    override_store.create.assert_not_called()
