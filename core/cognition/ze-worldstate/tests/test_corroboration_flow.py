"""Phase 172 integration: gate admission → match → corroborate/promote, through `LoopInflow`.

A stateful in-memory loop store stands in for Postgres so the match, the source rows and the
confidence arithmetic run together. The seam is bypassed as in `test_admission.py`.
"""

from __future__ import annotations

from tests.commitment_fixtures import conversation_admit

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_memory.graph.types import Relationship
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import review
from ze_worldstate.admission import LoopInflow
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.types import (
    LoopClaimKind,
    LoopSource,
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
)

TITLE = "Reply to Ana about the budget"
GATE_BARS = {
    "enabled": True,
    "loop_hold": 0.5,
    "explicit_hold": 0.6,
    "resolves_hold": 0.7,
}
CORR_BARS = {"enabled": True, "corroborate_hold": 0.6, "promote_hold": 0.85}


def _settings(corroboration=CORR_BARS):
    surfaces = {"loop_gate": GATE_BARS}
    if corroboration is not None:
        surfaces["corroboration"] = corroboration
    return {"system_one": {"surfaces": surfaces}}


@pytest.fixture(autouse=True)
def _bypass_seam(monkeypatch):
    from ze_worldstate import extraction

    async def submit(contribution, write, **kw):
        return await write()

    monkeypatch.setattr(extraction, "submit_and_detect_collisions", submit)


class FakeLoopStore:
    def __init__(self):
        self.loops: dict[UUID, OpenLoop] = {}
        self.entity_links: dict[UUID, set[UUID]] = {}
        self.evidence: dict[UUID, list[EvidenceRef]] = {}
        self.sources: dict[UUID, list[LoopSource]] = {}
        self.corroboration_recorded: list[UUID] = []
        self.deleted_sources = 0

    async def create(self, loop):
        loop = replace(loop, id=uuid4())
        self.loops[loop.id] = loop
        return loop

    async def get(self, loop_id):
        return self.loops.get(loop_id)

    async def list(self, states=None):
        return [
            loop
            for loop in self.loops.values()
            if not states or loop.state.value in states
        ]

    async def link_entity(self, loop_id, entity_id):
        self.entity_links.setdefault(entity_id, set()).add(loop_id)

    async def link_evidence(self, loop_id, kind, evidence_id):
        refs = self.evidence.setdefault(loop_id, [])
        ref = EvidenceRef(kind=kind, id=evidence_id)
        if ref not in refs:
            refs.append(ref)

    async def list_evidence(self, loop_id):
        return list(self.evidence.get(loop_id, []))

    async def set_confidence(self, loop_id, confidence):
        self.loops[loop_id].confidence = confidence

    async def set_drift_deadline(self, loop_id, deadline):
        self.loops[loop_id].drift_deadline = deadline

    async def set_dismissed_evidence_fingerprint(self, loop_id, fingerprint):
        self.loops[loop_id].dismissed_evidence_fingerprint = fingerprint

    async def record_corroboration(self, loop_id, **kw):
        self.corroboration_recorded.append(loop_id)

    async def transition(self, loop_id, new_state, **kw):
        self.loops[loop_id].state = LoopState(new_state)
        return self.loops[loop_id]

    async def add_source(self, source):
        rows = self.sources.setdefault(source.loop_id, [])
        if any(r.key == source.key for r in rows):
            return None
        row = replace(source, id=uuid4(), created_at=datetime.now(timezone.utc))
        rows.append(row)
        return row

    async def list_sources(self, loop_id):
        return list(self.sources.get(loop_id, []))

    async def promote(self, loop_id, *, confidence, window_days):
        loop = self.loops[loop_id]
        if loop.state is not LoopState.SUSPECTED:
            return None
        loop.state = LoopState.ACTIVE
        loop.confidence = max(loop.confidence, confidence)
        loop.drift_deadline = datetime.now(timezone.utc) + timedelta(days=window_days)
        return loop

    async def mark_source_promoted(self, source_id):
        for rows in self.sources.values():
            for i, row in enumerate(rows):
                if row.id == source_id:
                    rows[i] = replace(row, promoted=True)

    async def delete_source(self, *a, **kw):  # never expected to be called
        self.deleted_sources += 1


class FakeGraph:
    def __init__(self, store: FakeLoopStore):
        self._store = store

    async def list_relationships(self, entity_ids, predicates=None):
        return [
            Relationship(
                source_id=entity_id,
                source_type="entity",
                predicate="has_open_loop",
                target_id=loop_id,
                target_type="open_loop",
            )
            for entity_id in entity_ids
            for loop_id in self._store.entity_links.get(entity_id, ())
        ]


class FakeSystemOne:
    """Answers the gate as an open concern and `same_concern` with a settable score."""

    def __init__(self, same: float | SystemOneResult | Exception | None = 0.9):
        self.same = same
        self.same_calls: list[dict] = []
        self.gate_calls = 0

    async def evaluate(self, state, questions, *, max_attempts=None):
        if "same_concern" in questions:
            self.same_calls.append(state)
            if isinstance(self.same, Exception):
                raise self.same
            if isinstance(self.same, SystemOneResult):
                return self.same
            return SystemOneResult(
                outcome="ok",
                model="m",
                latency_ms=7,
                answers={"same_concern": SystemOneAnswer(type="noul", noul=self.same)},
            )
        self.gate_calls += 1
        answers = {
            "is_open_concern": SystemOneAnswer(type="noul", noul=0.9),
            "resolves_existing": SystemOneAnswer(type="noul", noul=0.0),
            "explicit_declaration": SystemOneAnswer(type="noul", noul=0.0),
        }
        return SystemOneResult(outcome="ok", answers=answers, latency_ms=5)


class WriterLLM:
    def __init__(self, title=TITLE):
        self.title = title

    async def complete(self, messages, **kw):
        return json.dumps({"title": self.title})


class Harness:
    def __init__(self, same=0.9, settings=None, title=TITLE, entity=None):
        self.store = FakeLoopStore()
        self.client = FakeSystemOne(same)
        self.entity = entity or uuid4()
        embedder = AsyncMock()
        embedder.encode = lambda text: [1.0, 0.0]
        self.inflow = LoopInflow(
            loop_store=self.store,
            graph_store=FakeGraph(self.store),
            entity_resolver=AsyncMock(return_value=[self.entity]),
            llm_client=WriterLLM(title),
            embedder=embedder,
            system_one_client=self.client,
            settings=_settings() if settings is None else settings,
        )

    @property
    def loop(self) -> OpenLoop:
        [loop] = [
            loop
            for loop in self.store.loops.values()
            if loop.state is not LoopState.DROPPED
        ]
        return loop

    async def chat(self, thread="th1", text="I need to reply to Ana about the budget"):
        ev = EvidenceRef(kind="episode", id=uuid4())
        adm = await conversation_admit(self.inflow, {"thread_id": thread}, prompt=text)
        await adm.commit([ev])
        return ev

    async def inbound(self, inflow, ref, evidence=None, text="Ana is waiting on the budget reply"):
        ev = evidence if evidence is not None else [EvidenceRef(kind="episode", id=uuid4())]
        await self.inflow.extract(text, inflow, evidence=ev, source_ref=ref)
        return ev

    def keys(self, loop=None):
        loop = loop or self.loop
        return [(s.role.value, s.key.inflow, s.promoted) for s in self.store.sources[loop.id]]


# ---- US1 ------------------------------------------------------------------


async def test_admit_puts_the_thread_key_on_the_admission():
    h = Harness()
    adm = await conversation_admit(h.inflow, {"thread_id": "th1"}, prompt="I need to reply to Ana")
    assert adm.source == SourceKey("conversation", "th1")
    assert (await conversation_admit(h.inflow, {}, prompt="I need to reply to Ana")).source is None


async def test_independent_email_promotes_a_suspected_loop():
    h = Harness(same=0.93)
    await h.chat()
    await h.inbound("email", "G1")

    loop = h.loop
    assert loop.state is LoopState.ACTIVE
    assert loop.confidence == pytest.approx(0.7)
    assert h.keys() == [("origin", "conversation", False), ("corroboration", "email", True)]
    assert len(h.client.same_calls) == 1
    assert h.client.same_calls[0]["loop"] == TITLE


async def test_corroborate_band_raises_confidence_and_stays_suspected():
    h = Harness(same=0.7)
    await h.chat()
    await h.inbound("email", "G1")

    loop = h.loop
    assert loop.state is LoopState.SUSPECTED
    assert loop.confidence == pytest.approx(1 - 0.7 * (1 - 0.5 * 0.7))
    assert h.keys()[1] == ("corroboration", "email", False)


async def test_third_source_promotes_a_loop_capped_at_point_six():
    h = Harness(same=0.8)
    await h.chat()
    await h.inbound("email", "G1")
    h.client.same = 0.7
    await h.inbound("calendar", "evt-1")
    assert h.loop.confidence == pytest.approx(0.6)
    assert h.loop.state is LoopState.SUSPECTED

    h.client.same = 0.95
    await h.inbound("ingestion", "doc-1")
    assert h.loop.state is LoopState.ACTIVE
    assert h.loop.confidence == pytest.approx(0.7)
    assert [k[1] for k in h.keys()] == ["conversation", "email", "calendar", "ingestion"]


async def test_origin_row_is_written_for_each_create_path_with_a_key():
    h = Harness()
    await h.chat()
    assert h.keys() == [("origin", "conversation", False)]

    h2 = Harness()
    await h2.inbound("email", "G1")
    assert h2.keys() == [("origin", "email", False)]


async def test_no_origin_row_without_a_key():
    h = Harness()
    await h.inflow.extract(
        "Ana is waiting", "email", evidence=[EvidenceRef(kind="episode", id=uuid4())]
    )
    assert h.store.sources == {}
    assert h.loop.state is LoopState.SUSPECTED


async def test_declared_path_match_corroborates_a_suspected_loop():
    h = Harness(same=0.93)
    await h.inbound("email", "G1")
    adm = await conversation_admit(h.inflow, {"thread_id": "th9"}, prompt="remind me to reply to Ana")
    adm.decision = replace(adm.decision, kind="create_declared", reason="explicit")
    await adm.commit([EvidenceRef(kind="episode", id=uuid4())])

    assert h.loop.state is LoopState.ACTIVE
    assert h.loop.confidence == pytest.approx(0.7)
    assert ("corroboration", "conversation", True) in h.keys()


# ---- US2 ------------------------------------------------------------------


@pytest.mark.parametrize(
    "second_inflow,second_ref",
    [("email", "G1"), ("conversation", "th1")],
)
async def test_same_source_never_corroborates_itself(second_inflow, second_ref):
    h = Harness(same=0.99)
    if second_inflow == "email":
        await h.inbound("email", "G1")
    else:
        await h.chat("th1")
    ev = await h.inbound(second_inflow, second_ref)

    assert h.client.same_calls == []
    loop = h.loop
    assert loop.state is LoopState.SUSPECTED and loop.confidence == pytest.approx(0.3)
    assert len(h.store.sources[loop.id]) == 1
    assert ev[0] in h.store.evidence[loop.id]


async def test_already_linked_evidence_is_not_corroboration():
    h = Harness(same=0.99)
    ev = await h.chat()
    await h.inbound("email", "G1", evidence=[ev])

    assert h.client.same_calls == []
    assert h.loop.confidence == pytest.approx(0.3)


async def test_no_key_never_corroborates():
    h = Harness(same=0.99)
    await h.chat()
    await h.inflow.extract(
        "Ana is waiting", "email", evidence=[EvidenceRef(kind="episode", id=uuid4())]
    )
    assert h.client.same_calls == []
    assert h.loop.state is LoopState.SUSPECTED


async def test_a_second_chat_thread_is_judged():
    h = Harness(same=0.7)
    await h.chat("th1")
    await h.chat("th2")
    assert len(h.client.same_calls) == 1
    assert ("corroboration", "conversation", False) in h.keys()


# ---- US3 ------------------------------------------------------------------


async def test_same_person_different_matter_is_not_corroboration():
    h = Harness(same=0.08, title="RSVP to Ana's party")
    await h.chat()
    ev = await h.inbound("email", "G1")

    loop = h.loop
    assert loop.state is LoopState.SUSPECTED and loop.confidence == pytest.approx(0.3)
    assert len(h.store.sources[loop.id]) == 1
    assert ev[0] in h.store.evidence[loop.id]
    assert len(h.client.same_calls) == 1


# ---- US4 ------------------------------------------------------------------


async def _with_dropped(h: Harness, dropped_source=("email", "G1")):
    dropped = await h.store.create(
        OpenLoop(
            title=TITLE,
            claim_kind=LoopClaimKind.SUSPICION,
            provenance="email",
            confidence=0.3,
            state=LoopState.DROPPED,
        )
    )
    await h.store.link_entity(dropped.id, h.entity)
    await h.store.add_source(
        LoopSource(
            loop_id=dropped.id,
            role=LoopSourceRole.ORIGIN,
            key=SourceKey(*dropped_source),
        )
    )
    dropped.dismissed_evidence_fingerprint = compute_evidence_fingerprint(
        [EvidenceRef(kind="episode", id=uuid4())]
    )
    suspected = await h.store.create(
        OpenLoop(
            title=TITLE,
            claim_kind=LoopClaimKind.SUSPICION,
            provenance="conversation",
            confidence=0.3,
        )
    )
    await h.store.link_entity(suspected.id, h.entity)
    await h.store.add_source(
        LoopSource(
            loop_id=suspected.id,
            role=LoopSourceRole.ORIGIN,
            key=SourceKey("conversation", "th1"),
        )
    )
    return dropped, suspected


async def test_dropped_loops_source_cannot_corroborate():
    h = Harness(same=0.99)
    _, suspected = await _with_dropped(h)
    await h.inbound("email", "G1")

    assert h.client.same_calls == []
    assert h.store.loops[suspected.id].confidence == pytest.approx(0.3)
    assert len(h.store.sources[suspected.id]) == 1


async def test_a_different_source_than_the_dropped_one_is_judged():
    h = Harness(same=0.7)
    _, suspected = await _with_dropped(h)
    await h.inbound("email", "G2")

    assert len(h.client.same_calls) == 1
    assert len(h.store.sources[suspected.id]) == 2


async def test_active_matches_are_never_judged():
    h = Harness(same=0.99)
    await h.chat()
    h.loop.state = LoopState.ACTIVE
    await h.inbound("email", "G1")

    assert h.client.same_calls == []
    assert h.store.corroboration_recorded == [h.loop.id]


async def test_closed_and_dropped_loops_are_never_judged():
    h = Harness(same=0.99)
    await h.chat()
    h.loop.state = LoopState.CLOSED
    await h.inbound("email", "G1")
    assert h.client.same_calls == []


async def test_dropping_a_promoted_loop_keeps_its_sources():
    h = Harness(same=0.93)
    await h.chat()
    await h.inbound("email", "G1")
    loop = h.loop
    assert loop.state is LoopState.ACTIVE

    await review.drop_loop(h.store, loop.id)

    assert h.store.deleted_sources == 0
    assert len(h.store.sources[loop.id]) == 2


# ---- US5 ------------------------------------------------------------------

_BAD_SURFACES = [
    {},
    {"enabled": False, "corroborate_hold": 0.6, "promote_hold": 0.85},
    {"enabled": True, "corroborate_hold": None, "promote_hold": 0.85},
    {"enabled": True, "corroborate_hold": 0.9, "promote_hold": 0.6},
]


@pytest.mark.parametrize("block", _BAD_SURFACES)
async def test_off_or_uncalibrated_surface_is_exactly_170(block):
    h = Harness(same=0.99, settings=_settings(block))
    await h.chat()
    ev = await h.inbound("email", "G1")

    assert h.client.same_calls == []
    loop = h.loop
    assert loop.state is LoopState.SUSPECTED and loop.confidence == pytest.approx(0.3)
    assert ev[0] in h.store.evidence[loop.id]
    assert h.keys() == [("origin", "conversation", False)]


async def test_origin_rows_are_written_with_the_surface_off():
    h = Harness(settings=_settings(None))
    await h.inbound("email", "G1")
    assert h.keys() == [("origin", "email", False)]


@pytest.mark.parametrize(
    "same",
    [
        SystemOneResult(outcome="skip", skip_reason="timeout"),
        RuntimeError("down"),
        SystemOneResult(outcome="ok", answers={}),
    ],
)
async def test_skip_exception_and_invalid_answer_are_exactly_170(same):
    h = Harness(same=same)
    await h.chat()
    ev = await h.inbound("email", "G1")

    loop = h.loop
    assert loop.state is LoopState.SUSPECTED and loop.confidence == pytest.approx(0.3)
    assert ev[0] in h.store.evidence[loop.id]
    assert len(h.store.sources[loop.id]) == 1
    assert len(h.client.same_calls) == 1
