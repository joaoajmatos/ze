from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_plugin.contribution import EvidenceRef
from ze_worldstate import review
from ze_worldstate.drift import DEFAULT_DRIFT_WINDOW_DAYS
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.types import (
    DECLARED_CONFIDENCE,
    LoopProvenance,
    LoopState,
    OpenLoop,
)


def _loop(state=LoopState.SUSPECTED, **overrides) -> OpenLoop:
    defaults = dict(
        id=uuid4(),
        title="Renew passport",
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        state=state,
    )
    defaults.update(overrides)
    return OpenLoop(**defaults)


async def test_confirm_loop_stamps_like_a_declaration():
    loop_store = AsyncMock()
    suspected = _loop(
        state=LoopState.ACTIVE,
        provenance="email",
        confirmed_at=datetime.now(timezone.utc),
    )
    loop_store.transition = AsyncMock(return_value=suspected)
    loop_id = uuid4()

    before = datetime.now(timezone.utc)
    result = await review.confirm_loop(loop_store, loop_id)

    loop_store.transition.assert_awaited_once_with(loop_id, "active")
    loop_store.stamp_declared.assert_awaited_once()
    kwargs = loop_store.stamp_declared.await_args.kwargs
    assert kwargs["confidence"] == DECLARED_CONFIDENCE
    expected = before + timedelta(days=DEFAULT_DRIFT_WINDOW_DAYS)
    assert abs((kwargs["deadline"] - expected).total_seconds()) < 5
    loop_store.set_drift_deadline.assert_not_called()
    assert result.state == LoopState.ACTIVE
    assert result.confidence == DECLARED_CONFIDENCE
    assert result.drift_rationale is None
    assert result.drift_deadline == kwargs["deadline"]
    assert result.provenance == "email"


@pytest.mark.parametrize("error", [InvalidLoopTransitionError("no"), LoopNotFoundError("x")])
async def test_confirm_loop_propagates_transition_errors_without_stamping(error):
    loop_store = AsyncMock()
    loop_store.transition = AsyncMock(side_effect=error)

    with pytest.raises(type(error)):
        await review.confirm_loop(loop_store, uuid4())

    loop_store.stamp_declared.assert_not_called()


async def test_close_loop_transitions_to_closed():
    loop_store = AsyncMock()
    closed_loop = _loop(state=LoopState.CLOSED)
    loop_store.transition = AsyncMock(return_value=closed_loop)

    result = await review.close_loop(loop_store, uuid4())
    assert result.state == LoopState.CLOSED


async def test_drop_loop_computes_and_persists_fingerprint():
    loop_id = uuid4()
    loop_store = AsyncMock()
    refs = [EvidenceRef(kind="episode", id=uuid4())]
    loop_store.list_evidence = AsyncMock(return_value=refs)
    dropped_loop = _loop(state=LoopState.DROPPED)
    loop_store.transition = AsyncMock(return_value=dropped_loop)
    loop_store.set_dismissed_evidence_fingerprint = AsyncMock()

    result = await review.drop_loop(loop_store, loop_id)

    loop_store.set_dismissed_evidence_fingerprint.assert_awaited_once()
    assert result.dismissed_evidence_fingerprint is not None
    assert result.state == LoopState.DROPPED


async def test_drop_loop_never_deletes_evidence_or_entities():
    """FR-013: drop only changes open_loops.state / dismissed_evidence_fingerprint,
    never memory_entities/memory_facts/memory_episodes or the loop's own links."""
    loop_id = uuid4()
    loop_store = AsyncMock()
    loop_store.list_evidence = AsyncMock(return_value=[])
    loop_store.transition = AsyncMock(return_value=_loop(state=LoopState.DROPPED))
    loop_store.set_dismissed_evidence_fingerprint = AsyncMock()

    await review.drop_loop(loop_store, loop_id)

    loop_store.transition.assert_awaited_once_with(loop_id, LoopState.DROPPED.value)
    loop_store.list_evidence.assert_awaited_once()
    loop_store.set_dismissed_evidence_fingerprint.assert_awaited_once()
