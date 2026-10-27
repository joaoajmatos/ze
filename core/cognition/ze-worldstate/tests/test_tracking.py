from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from ze_memory.graph.types import Relationship
from ze_worldstate import tracking
from ze_worldstate.errors import InvalidLoopTransitionError
from ze_worldstate.lifecycle import DeclaredStamp, LoopDraft, LoopLifecycle, Tracked
from ze_worldstate.tracking import LoopTracker
from ze_worldstate.types import (
    LoopProvenance,
    LoopState,
    OpenLoop,
    SourceKey,
    TrackOutcome,
)

_DEFAULT_WINDOW = 7


def _loop(**overrides) -> OpenLoop:
    base = dict(
        id=uuid4(),
        title="Porto move",
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        state=LoopState.SUSPECTED,
    )
    base.update(overrides)
    return OpenLoop(**base)


def _rel(target_id: UUID) -> Relationship:
    return Relationship(
        source_id=uuid4(),
        source_type="entity",
        predicate="has_open_loop",
        target_id=target_id,
        target_type="open_loop",
    )


class FakeLoopStore:
    """Reads only: a tracker writes through the lifecycle, never the store."""

    def __init__(self, loops: list[OpenLoop] | None = None) -> None:
        self.loops: dict[UUID, OpenLoop] = {loop.id: loop for loop in loops or []}

    async def get(self, loop_id: UUID) -> OpenLoop | None:
        return self.loops.get(loop_id)

    async def list(self, states: list[str] | None = None) -> list[OpenLoop]:
        loops = list(self.loops.values())
        if states is not None:
            loops = [loop for loop in loops if loop.state.value in states]
        return loops


class FakeGraphStore:
    def __init__(self, linked: list[UUID] | None = None) -> None:
        self.linked = list(linked or [])

    async def list_relationships(self, entity_ids, predicates=None):
        return [_rel(loop_id) for loop_id in self.linked]


class FakeEmbedder:
    def encode_passage(self, text: str) -> list[float]:
        return [1.0, 0.0] if "porto" in text.lower() else [0.0, 1.0]

    encode_query = encode_passage


def _lifecycle() -> AsyncMock:
    lifecycle = AsyncMock(spec=LoopLifecycle)

    async def _create_declared(draft: LoopDraft, *, window_days=None) -> OpenLoop:
        return OpenLoop(
            id=uuid4(),
            title=draft.title,
            provenance=draft.provenance,
            confidence=DeclaredStamp.CONFIDENCE,
            state=LoopState.ACTIVE,
        )

    lifecycle.create_declared.side_effect = _create_declared
    return lifecycle


def _tracked(outcome: str, loop: OpenLoop) -> Tracked:
    return Tracked(outcome=outcome, loop=loop)


def _build(
    store: FakeLoopStore,
    graph: FakeGraphStore,
    entity_resolver,
    lifecycle: AsyncMock,
) -> LoopTracker:
    return LoopTracker(
        loop_store=store,
        lifecycle=lifecycle,
        graph_store=graph,
        entity_resolver=entity_resolver,
        embedder=FakeEmbedder(),
    )


async def test_no_match_creates_a_declared_loop_with_a_conversation_origin():
    entity_id = uuid4()
    lifecycle = _lifecycle()
    tracker = _build(FakeLoopStore(), FakeGraphStore(), _resolver(entity_id), lifecycle)

    result = await tracker.track("Decide about the Porto move", session_id="thread-1")

    assert result.ok is True
    assert result.outcome == TrackOutcome.CREATED
    assert result.loop.state == LoopState.ACTIVE
    lifecycle.create_declared.assert_awaited_once_with(
        LoopDraft(
            title="Decide about the Porto move",
            provenance=LoopProvenance.USER_DECLARED,
            entity_ids=(entity_id,),
            source=SourceKey(LoopProvenance.CONVERSATION, "thread-1"),
        ),
        window_days=_DEFAULT_WINDOW,
    )
    lifecycle.track.assert_not_awaited()


async def test_create_carries_no_evidence():
    lifecycle = _lifecycle()
    tracker = _build(FakeLoopStore(), FakeGraphStore(), _resolver(uuid4()), lifecycle)

    await tracker.track("Porto move", session_id="thread-1")

    draft = lifecycle.create_declared.await_args.args[0]
    assert draft.evidence == ()


async def test_create_without_a_session_has_no_origin_source():
    lifecycle = _lifecycle()
    tracker = _build(FakeLoopStore(), FakeGraphStore(), _resolver(uuid4()), lifecycle)

    await tracker.track("Porto move")

    assert lifecycle.create_declared.await_args.args[0].source is None


@pytest.mark.parametrize(
    "window_days,expected_days",
    [
        (14, 14),
        (0, _DEFAULT_WINDOW),
        (-3, _DEFAULT_WINDOW),
        (True, _DEFAULT_WINDOW),
        ("x", _DEFAULT_WINDOW),
        (400, 365),
    ],
)
async def test_window_days_is_clamped(window_days, expected_days):
    lifecycle = _lifecycle()
    tracker = _build(FakeLoopStore(), FakeGraphStore(), _resolver(uuid4()), lifecycle)

    await tracker.track("Porto move", window_days)

    assert lifecycle.create_declared.await_args.kwargs["window_days"] == expected_days


async def test_default_window_is_the_declared_stamp_window():
    assert tracking.DEFAULT_WINDOW_DAYS == DeclaredStamp.DEFAULT_WINDOW_DAYS


async def test_empty_title_writes_nothing():
    lifecycle = _lifecycle()
    tracker = _build(FakeLoopStore(), FakeGraphStore(), _resolver(uuid4()), lifecycle)

    result = await tracker.track("   ")

    assert result.ok is False
    assert result.error
    assert lifecycle.method_calls == []


async def test_title_is_normalized_and_capped():
    lifecycle = _lifecycle()
    tracker = _build(FakeLoopStore(), FakeGraphStore(), _resolver(uuid4()), lifecycle)

    spaced = await tracker.track("  Porto   move  ")
    assert spaced.loop.title == "Porto move"

    capped = await tracker.track(" ".join(["Porto"] * 100))
    assert len(capped.loop.title) <= 120
    assert capped.loop.title.endswith("Porto")
    assert not capped.loop.title.endswith(" ")


@pytest.mark.parametrize(
    ("state", "outcome"),
    [
        (LoopState.SUSPECTED, TrackOutcome.CONFIRMED),
        (LoopState.ACTIVE, TrackOutcome.REINFORCED),
        (LoopState.DRIFTING, TrackOutcome.REVIVED),
    ],
)
async def test_a_match_is_tracked_through_the_lifecycle(state, outcome):
    existing = _loop(state=state)
    entity_id = uuid4()
    lifecycle = _lifecycle()
    lifecycle.track.return_value = _tracked(outcome, existing)
    tracker = _build(
        FakeLoopStore([existing]),
        FakeGraphStore([existing.id]),
        _resolver(entity_id),
        lifecycle,
    )

    result = await tracker.track("Porto move", 14, session_id="thread-1")

    assert result.ok is True
    assert result.outcome == outcome
    assert result.loop is existing
    lifecycle.track.assert_awaited_once_with(
        existing.id, window_days=14, entity_ids=[entity_id]
    )
    lifecycle.create_declared.assert_not_awaited()


async def test_dropped_match_does_not_block_creation():
    dropped = _loop(state=LoopState.DROPPED)
    lifecycle = _lifecycle()
    tracker = _build(
        FakeLoopStore([dropped]),
        FakeGraphStore([dropped.id]),
        _resolver(uuid4()),
        lifecycle,
    )

    result = await tracker.track("Porto move")

    assert result.outcome == TrackOutcome.CREATED
    lifecycle.create_declared.assert_awaited_once()
    lifecycle.track.assert_not_awaited()


async def test_resolver_error_fails_open():
    async def broken_resolver(text):
        raise RuntimeError("boom")

    lifecycle = _lifecycle()
    tracker = _build(FakeLoopStore(), FakeGraphStore(), broken_resolver, lifecycle)

    result = await tracker.track("Porto move")

    assert result.ok is True
    assert result.outcome == TrackOutcome.CREATED
    assert lifecycle.create_declared.await_args.args[0].entity_ids == ()


async def test_create_error_is_returned_not_raised():
    lifecycle = _lifecycle()
    lifecycle.create_declared.side_effect = RuntimeError("db down")
    tracker = _build(FakeLoopStore(), FakeGraphStore(), _resolver(uuid4()), lifecycle)

    result = await tracker.track("Porto move")

    assert result.ok is False
    assert result.error


async def test_track_refusal_is_returned_not_raised():
    existing = _loop(state=LoopState.DRIFTING)
    lifecycle = _lifecycle()
    lifecycle.track.side_effect = InvalidLoopTransitionError("lost race")
    tracker = _build(
        FakeLoopStore([existing]),
        FakeGraphStore([existing.id]),
        _resolver(uuid4()),
        lifecycle,
    )

    result = await tracker.track("Porto move")

    assert result.ok is False
    assert result.error


def _resolver(entity_id: UUID):
    async def _fn(text: str) -> list[UUID]:
        return [entity_id]

    return _fn
