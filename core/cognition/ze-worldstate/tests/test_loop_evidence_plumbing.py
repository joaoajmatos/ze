"""Phase 170/203: evidence reaches the lifecycle through the one commit; matches note it; the declared path dedups."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_plugin.contribution import EvidenceRef

from tests.commitment_fixtures import _BARS, commit_loop, conversation_admit, make
from ze_worldstate import admission
from ze_worldstate.admission import LoopInflow
from ze_worldstate.decision import CommitDecision
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.intake import CommitmentIntake
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop

BARS = {"enabled": True, "loop_hold": 0.5, "resolves_hold": 0.7}
TEXT = "I need to renew my passport"


def _loop(state=LoopState.ACTIVE, fingerprint=None) -> OpenLoop:
    return OpenLoop(
        id=uuid4(),
        title="Renew passport",
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.9,
        state=state,
        dismissed_evidence_fingerprint=fingerprint,
    )


def _ref() -> EvidenceRef:
    return EvidenceRef(kind="episode", id=uuid4())


class _Env:
    def __init__(self, monkeypatch, matches=None):
        self.lifecycle = AsyncMock(spec=LoopLifecycle)
        self.lifecycle.create_suspected.side_effect = lambda draft: _loop(
            LoopState.SUSPECTED
        )
        self.lifecycle.create_declared.side_effect = lambda draft, window_days=None: (
            _loop()
        )
        self.lifecycle.note_evidence.side_effect = (
            lambda loop_id, evidence, entity_ids: _loop()
        )
        self.loop_store = AsyncMock()
        self.loop_store.list = AsyncMock(return_value=[])
        self.graph_store = AsyncMock()
        self.matches = matches or {}

        async def find(entity_ids, title, *, states, **kw):
            return self.matches.get(tuple(states))

        monkeypatch.setattr(admission, "find_matching_loop", find)

    def inflow(self, llm=None, system_one=None, settings=None) -> LoopInflow:
        return LoopInflow(
            lifecycle=self.lifecycle,
            loop_store=self.loop_store,
            graph_store=self.graph_store,
            entity_resolver=AsyncMock(return_value=[]),
            llm_client=llm or AsyncMock(),
            embedder=AsyncMock(),
            system_one_client=system_one,
            settings=settings,
        )

    async def commit(self, kind, provenance, evidence, *, title="Renew passport"):
        return await self.inflow().commit(
            CommitDecision(kind, "test", title=title),
            text=TEXT,
            inflow=provenance,
            evidence=evidence,
        )


LIVE = ("suspected", "active", "drifting")


@pytest.mark.parametrize("state", [LoopState.ACTIVE, LoopState.DRIFTING])
async def test_declared_match_notes_evidence_on_the_existing_loop(monkeypatch, state):
    existing = _loop(state)
    env = _Env(monkeypatch, {LIVE: existing, ("dropped",): None})
    ref = _ref()

    result = await env.commit("create_declared", "conversation", [ref])

    assert result.outcome == "matched" and result.loops[0].id is not None
    env.lifecycle.create_declared.assert_not_awaited()
    env.lifecycle.note_evidence.assert_awaited_once_with(
        existing.id, evidence=(ref,), entity_ids=()
    )


async def test_a_match_with_no_evidence_still_goes_through_note_evidence(monkeypatch):
    existing = _loop(LoopState.ACTIVE)
    env = _Env(monkeypatch, {LIVE: existing})
    await env.commit("create_declared", "conversation", [])
    env.lifecycle.note_evidence.assert_awaited_once_with(
        existing.id, evidence=(), entity_ids=()
    )


async def test_declared_without_match_creates_with_the_evidence_on_the_draft(
    monkeypatch,
):
    env = _Env(monkeypatch)
    ref = _ref()

    result = await env.commit("create_declared", "conversation", [ref])

    assert result.outcome == "created" and len(result.loops) == 1
    draft = env.lifecycle.create_declared.await_args.args[0]
    assert draft.evidence == (ref,)
    env.lifecycle.note_evidence.assert_not_awaited()


async def test_haiku_gate_declared_path_also_dedups(monkeypatch):
    existing = _loop(LoopState.ACTIVE)
    env = _Env(monkeypatch, {LIVE: existing})
    llm = AsyncMock()
    llm.complete = AsyncMock(
        return_value=json.dumps(
            {"is_loop": True, "title": "Renew passport", "explicit_declaration": True}
        )
    )
    result = await env.inflow(llm).commit(
        CommitDecision("fallback", "disabled"),
        text=TEXT,
        inflow="conversation",
        evidence=[_ref()],
    )
    assert result.outcome == "matched" and result.loops[0].id is not None
    env.lifecycle.create_declared.assert_not_awaited()


async def test_a_suspected_create_that_matches_an_active_loop_notes_the_evidence(
    monkeypatch,
):
    env = _Env(monkeypatch, {LIVE: _loop(LoopState.ACTIVE)})
    ref = _ref()
    result = await env.commit("create_suspected", "email", [ref])
    assert result.outcome == "matched"
    env.lifecycle.note_evidence.assert_awaited_once()
    assert env.lifecycle.note_evidence.await_args.kwargs["evidence"] == (ref,)
    env.lifecycle.create_suspected.assert_not_awaited()


A, B = _ref(), _ref()


@pytest.mark.parametrize(
    "dropped_evidence,new_evidence,suppressed",
    [([A], [A], True), ([A], [B], False), ([], [], True), ([], [B], False)],
)
async def test_dismissal_fingerprint_semantics(
    monkeypatch, dropped_evidence, new_evidence, suppressed
):
    dropped = _loop(
        LoopState.DROPPED, fingerprint=compute_evidence_fingerprint(dropped_evidence)
    )
    env = _Env(monkeypatch, {("dropped",): dropped})
    result = await env.commit("create_suspected", "email", new_evidence)
    assert (result.outcome == "dismissed") is suppressed
    assert (env.lifecycle.create_suspected.await_count == 0) is suppressed


def _system_one_positive():
    class S1:
        async def evaluate(self, state, questions, *, max_attempts=None):
            return SystemOneResult(
                outcome="ok",
                answers={
                    "is_open_concern": SystemOneAnswer(type="noul", noul=0.9),
                    "resolves_existing": SystemOneAnswer(type="noul", noul=0.0),
                },
                latency_ms=1,
            )

    return S1()


def _inflow(monkeypatch):
    env = _Env(monkeypatch)
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=json.dumps({"title": "Renew passport"}))
    inflow = env.inflow(
        llm, _system_one_positive(), {"system_one": {"surfaces": {"loop_gate": BARS}}}
    )
    return inflow, env


async def test_admission_commit_takes_evidence_and_passes_it_to_the_lifecycle(
    monkeypatch,
):
    inflow, env = _inflow(monkeypatch)
    ref = _ref()

    class CommitmentS1:
        async def evaluate(self, state, questions, *, max_attempts=None):
            return make("loop", explicit=0.1)

    intake = CommitmentIntake(
        loop_inflow=inflow,
        lifecycle=env.lifecycle,
        loop_store=env.loop_store,
        graph_store=env.graph_store,
        entity_resolver=AsyncMock(return_value=[]),
        embedder=AsyncMock(),
        system_one_client=CommitmentS1(),
        settings={
            "system_one": {
                "surfaces": {"commitment_intake": {"enabled": True, **_BARS}}
            }
        },
    )
    adm = await conversation_admit(
        intake, {}, prompt="Daniel is still waiting on my answer to the passport form"
    )

    result = await commit_loop(inflow, adm, [ref])

    assert len(result.loops) == 1
    draft = env.lifecycle.create_suspected.await_args.args[0]
    assert draft.evidence == (ref,)


async def test_extract_forwards_evidence_through_the_commit(monkeypatch):
    inflow, env = _inflow(monkeypatch)
    ref = _ref()

    await inflow.extract(
        "Daniel is still waiting on my answer to the passport form",
        "email",
        evidence=[ref],
    )

    draft = env.lifecycle.create_suspected.await_args.args[0]
    assert draft.evidence == (ref,)


async def test_extract_without_evidence_still_works(monkeypatch):
    inflow, env = _inflow(monkeypatch)
    await inflow.extract(
        "Daniel is still waiting on my answer to the passport form", "calendar"
    )
    draft = env.lifecycle.create_suspected.await_args.args[0]
    assert draft.evidence == ()
