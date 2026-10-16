from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from ze_agents.claims import ClaimKind
from ze_memory.graph.types import Relationship
from ze_worldstate import tracking
from ze_worldstate.errors import InvalidLoopTransitionError
from ze_worldstate.tracking import LoopTracker
from ze_worldstate.types import (
    LoopProvenance,
    LoopState,
    OpenLoop,
    TrackOutcome,
)

_DEFAULT_WINDOW = 7


def _loop(**overrides) -> OpenLoop:
    base = dict(
        id=uuid4(),
        title="Porto move",
        claim_kind=ClaimKind.SUSPICION,
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
    def __init__(self, loops: list[OpenLoop] | None = None) -> None:
        self.loops: dict[UUID, OpenLoop] = {loop.id: loop for loop in loops or []}
        self.created: list[OpenLoop] = []
        self.transitions: list[tuple[UUID, str, bool]] = []
        self.stamp_calls: list[tuple[UUID, float]] = []
        self.confidence_calls: list[tuple[UUID, float]] = []
        self.linked_entity_ids: list[UUID] = []
        self.create_error: Exception | None = None
        self.transition_error: Exception | None = None

    async def create(self, loop: OpenLoop) -> OpenLoop:
        if self.create_error is not None:
            raise self.create_error
        loop.id = loop.id or uuid4()
        self.loops[loop.id] = loop
        self.created.append(loop)
        return loop

    async def get(self, loop_id: UUID) -> OpenLoop | None:
        return self.loops.get(loop_id)

    async def list(self, states: list[str] | None = None) -> list[OpenLoop]:
        loops = list(self.loops.values())
        if states is not None:
            loops = [loop for loop in loops if loop.state.value in states]
        return loops

    async def transition(
        self, loop_id: UUID, new_state: str, *, user_asked: bool = False
    ) -> OpenLoop:
        if self.transition_error is not None:
            raise self.transition_error
        loop = self.loops[loop_id]
        loop.state = LoopState(new_state)
        self.transitions.append((loop_id, new_state, user_asked))
        return loop

    async def stamp_declared(
        self, loop_id: UUID, *, confidence: float, deadline
    ) -> None:
        self.stamp_calls.append((loop_id, confidence))

    async def set_confidence(self, loop_id: UUID, confidence: float) -> None:
        self.confidence_calls.append((loop_id, confidence))
        self.loops[loop_id].confidence = confidence

    async def link_entity(self, loop_id: UUID, entity_id: UUID) -> None:
        self.linked_entity_ids.append(entity_id)


class FakeGraphStore:
    def __init__(self, linked: list[UUID] | None = None) -> None:
        self.linked = list(linked or [])

    async def list_relationships(self, entity_ids, predicates=None):
        return [_rel(loop_id) for loop_id in self.linked]


class FakeEmbedder:
    def encode_passage(self, text: str) -> list[float]:
        return [1.0, 0.0] if "porto" in text.lower() else [0.0, 1.0]
    encode_query = encode_passage


class SeamRecorder:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, contribution, write, *, result_id, producer_kind, **kwargs):
        self.calls.append(
            {"contribution": contribution, "producer_kind": producer_kind}
        )
        return await write()


@pytest.fixture
def seam(monkeypatch) -> SeamRecorder:
    recorder = SeamRecorder()
    monkeypatch.setattr(tracking, "submit_and_detect_collisions", recorder)
    return recorder


def _build(
    store: FakeLoopStore,
    graph: FakeGraphStore,
    entity_resolver,
) -> LoopTracker:
    return LoopTracker(
        loop_store=store,
        graph_store=graph,
        entity_resolver=entity_resolver,
        embedder=FakeEmbedder(),
    )


async def test_no_match_creates_user_declared_active_loop(seam):
    entity_id = uuid4()
    store = FakeLoopStore()
    tracker = _build(store, FakeGraphStore(), _resolver(entity_id))

    result = await tracker.track("Decide about the Porto move")

    assert result.ok is True
    assert result.outcome == TrackOutcome.CREATED
    loop = result.loop
    assert loop.state == LoopState.ACTIVE
    assert loop.provenance == LoopProvenance.USER_DECLARED
    assert loop.claim_kind == ClaimKind.PRIORITY
    assert loop.confidence == 0.9
    assert loop.confirmed_at is not None
    assert loop.drift_deadline - loop.confirmed_at == timedelta(days=_DEFAULT_WINDOW)
    assert len(store.created) == 1
    assert store.stamp_calls and store.stamp_calls[0][1] == 0.9
    assert len(seam.calls) == 1
    assert seam.calls[0]["producer_kind"] == "open_loop"
    assert store.linked_entity_ids == [entity_id]


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
async def test_window_days_is_clamped(seam, window_days, expected_days):
    store = FakeLoopStore()
    tracker = _build(store, FakeGraphStore(), _resolver(uuid4()))

    result = await tracker.track("Porto move", window_days)

    assert result.loop.drift_deadline - result.loop.confirmed_at == timedelta(
        days=expected_days
    )


async def test_empty_title_writes_nothing(seam):
    store = FakeLoopStore()
    tracker = _build(store, FakeGraphStore(), _resolver(uuid4()))

    result = await tracker.track("   ")

    assert result.ok is False
    assert result.error
    assert store.created == []
    assert seam.calls == []


async def test_title_is_normalized_and_capped(seam):
    store = FakeLoopStore()
    tracker = _build(store, FakeGraphStore(), _resolver(uuid4()))

    spaced = await tracker.track("  Porto   move  ")
    assert spaced.loop.title == "Porto move"

    long_title = " ".join(["Porto"] * 100)
    fresh = _build(FakeLoopStore(), FakeGraphStore(), _resolver(uuid4()))
    capped = await fresh.track(long_title)
    assert len(capped.loop.title) <= 120
    assert capped.loop.title.endswith("Porto")
    assert not capped.loop.title.endswith(" ")


async def test_matching_suspected_loop_is_confirmed(seam):
    existing = _loop(state=LoopState.SUSPECTED)
    store = FakeLoopStore([existing])
    tracker = _build(store, FakeGraphStore([existing.id]), _resolver(uuid4()))

    result = await tracker.track("Porto move")

    assert result.outcome == TrackOutcome.CONFIRMED
    assert store.created == []
    assert store.transitions == [(existing.id, "active", False)]
    assert store.stamp_calls == [(existing.id, 0.9)]
    assert result.loop.state == LoopState.ACTIVE
    assert result.loop.confidence == 0.9


async def test_matching_active_loop_is_reinforced(seam):
    existing = _loop(state=LoopState.ACTIVE, confidence=0.8)
    store = FakeLoopStore([existing])
    entity_id = uuid4()
    tracker = _build(store, FakeGraphStore([existing.id]), _resolver(entity_id))

    result = await tracker.track("Porto move")

    assert result.outcome == TrackOutcome.REINFORCED
    assert store.created == []
    assert store.transitions == []
    assert store.confidence_calls == [(existing.id, 0.9)]
    assert result.loop.confidence == 0.9
    assert store.linked_entity_ids == [entity_id]


async def test_reinforce_never_lowers_confidence(seam):
    existing = _loop(state=LoopState.ACTIVE, confidence=0.95)
    store = FakeLoopStore([existing])
    tracker = _build(store, FakeGraphStore([existing.id]), _resolver(uuid4()))

    result = await tracker.track("Porto move")

    assert result.outcome == TrackOutcome.REINFORCED
    assert store.confidence_calls == [(existing.id, 0.95)]
    assert result.loop.confidence == 0.95


async def test_matching_drifting_loop_is_revived(seam):
    existing = _loop(state=LoopState.DRIFTING, confidence=0.4)
    store = FakeLoopStore([existing])
    tracker = _build(store, FakeGraphStore([existing.id]), _resolver(uuid4()))

    result = await tracker.track("Porto move")

    assert result.outcome == TrackOutcome.REVIVED
    assert store.created == []
    assert store.transitions == [(existing.id, "active", True)]
    assert store.stamp_calls == [(existing.id, 0.9)]
    assert result.loop.state == LoopState.ACTIVE
    assert result.loop.drift_rationale is None


async def test_dropped_match_does_not_block_creation(seam):
    dropped = _loop(state=LoopState.DROPPED)
    store = FakeLoopStore([dropped])
    tracker = _build(store, FakeGraphStore([dropped.id]), _resolver(uuid4()))

    result = await tracker.track("Porto move")

    assert result.outcome == TrackOutcome.CREATED
    assert len(store.created) == 1
    assert store.loops[dropped.id].state == LoopState.DROPPED


async def test_resolver_error_fails_open(seam):
    async def broken_resolver(text):
        raise RuntimeError("boom")

    store = FakeLoopStore()
    tracker = _build(store, FakeGraphStore(), broken_resolver)

    result = await tracker.track("Porto move")

    assert result.ok is True
    assert result.outcome == TrackOutcome.CREATED
    assert store.linked_entity_ids == []


async def test_store_create_error_is_returned_not_raised(seam):
    store = FakeLoopStore()
    store.create_error = RuntimeError("db down")
    tracker = _build(store, FakeGraphStore(), _resolver(uuid4()))

    result = await tracker.track("Porto move")

    assert result.ok is False
    assert result.error


async def test_revive_transition_error_is_returned_not_raised(seam):
    existing = _loop(state=LoopState.DRIFTING)
    store = FakeLoopStore([existing])
    store.transition_error = InvalidLoopTransitionError("lost race")
    tracker = _build(store, FakeGraphStore([existing.id]), _resolver(uuid4()))

    result = await tracker.track("Porto move")

    assert result.ok is False
    assert result.error


def _resolver(entity_id: UUID):
    async def _fn(text: str) -> list[UUID]:
        return [entity_id]

    return _fn
