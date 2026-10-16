"""Phase 170: evidence reaches the loop commit; matches corroborate; the declared path dedups."""

from __future__ import annotations

from tests.commitment_fixtures import conversation_admit

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import extraction
from ze_worldstate.admission import LoopInflow
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.types import LoopClaimKind, LoopProvenance, LoopState, OpenLoop

BARS = {"enabled": True, "loop_hold": 0.5, "explicit_hold": 0.6, "resolves_hold": 0.7}


def _loop(state=LoopState.ACTIVE, fingerprint=None) -> OpenLoop:
    return OpenLoop(
        id=uuid4(),
        title="Renew passport",
        claim_kind=LoopClaimKind.PRIORITY,
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.9,
        state=state,
        dismissed_evidence_fingerprint=fingerprint,
    )


def _ref() -> EvidenceRef:
    return EvidenceRef(kind="episode", id=uuid4())


class _Env:
    def __init__(self, monkeypatch, matches=None):
        self.submit_kwargs: dict = {}
        self.loop_store = AsyncMock()
        self.loop_store.create = AsyncMock(side_effect=self._create)
        self.loop_store.list = AsyncMock(return_value=[])
        self.graph_store = AsyncMock()
        self.memory_store = AsyncMock()
        self.matches = matches or {}

        async def submit(contribution, write, **kw):
            self.submit_kwargs = kw
            return await write()

        async def find(entity_ids, title, *, states, **kw):
            return self.matches.get(tuple(states))

        monkeypatch.setattr(extraction, "submit_and_detect_collisions", submit)
        monkeypatch.setattr(extraction, "find_matching_loop", find)

    @staticmethod
    async def _create(loop):
        loop.id = uuid4()
        return loop

    async def propose(self, provenance, evidence, *, title="Renew passport", explicit=None):
        explicit = provenance == "user_declared" if explicit is None else explicit
        llm = AsyncMock()
        llm.complete = AsyncMock(
            return_value=json.dumps(
                {"is_loop": True, "title": title, "explicit_declaration": explicit}
            )
        )
        return await extraction.propose_loop_candidates(
            "I need to renew my passport",
            provenance,
            evidence,
            llm,
            AsyncMock(),
            self.loop_store,
            AsyncMock(return_value=[]),
            graph_store=self.graph_store,
            memory_store=self.memory_store,
        )


LIVE = ("suspected", "active", "drifting")


async def test_declared_match_links_evidence_and_corroborates_active_loop(monkeypatch):
    existing = _loop(LoopState.ACTIVE)
    env = _Env(monkeypatch, {LIVE: existing})
    ref = _ref()

    result = await env.propose("user_declared", [ref])

    assert result == [existing]
    env.loop_store.create.assert_not_awaited()
    env.loop_store.link_evidence.assert_awaited_once_with(existing.id, "episode", ref.id)
    env.loop_store.record_corroboration.assert_awaited_once_with(existing.id)
    assert existing.state is LoopState.ACTIVE and existing.confidence == 0.9


@pytest.mark.parametrize("state", [LoopState.SUSPECTED, LoopState.DRIFTING])
async def test_declared_match_does_not_corroborate_non_active_loops(monkeypatch, state):
    env = _Env(monkeypatch, {LIVE: _loop(state)})
    await env.propose("user_declared", [_ref()])
    env.loop_store.record_corroboration.assert_not_awaited()


async def test_declared_match_without_evidence_does_not_corroborate(monkeypatch):
    env = _Env(monkeypatch, {LIVE: _loop(LoopState.ACTIVE)})
    await env.propose("user_declared", [])
    env.loop_store.record_corroboration.assert_not_awaited()


async def test_declared_without_match_creates_and_passes_existence_checkers(monkeypatch):
    env = _Env(monkeypatch)
    ref = _ref()

    result = await env.propose("user_declared", [ref])

    assert len(result) == 1
    env.loop_store.create.assert_awaited_once()
    assert callable(env.submit_kwargs["check_episode_exists"])
    assert callable(env.submit_kwargs["check_fact_exists"])
    env.memory_store.get_episodes_by_ids.return_value = [object()]
    assert await env.submit_kwargs["check_episode_exists"](ref.id) is True


async def test_haiku_gate_declared_path_also_dedups(monkeypatch):
    existing = _loop(LoopState.ACTIVE)
    env = _Env(monkeypatch, {LIVE: existing})
    result = await env.propose("conversation", [_ref()], explicit=True)
    assert result == [existing]
    env.loop_store.create.assert_not_awaited()


async def test_suspected_match_corroborates_only_active_with_evidence(monkeypatch):
    async def run(match_state, evidence):
        env = _Env(monkeypatch, {LIVE: _loop(match_state)})
        llm = AsyncMock()
        llm.complete = AsyncMock(
            return_value=json.dumps({"is_loop": True, "title": "Renew passport", "explicit_declaration": False})
        )
        await extraction.propose_loop_candidates(
            "maybe renew passport", "email", evidence, llm, AsyncMock(), env.loop_store,
            AsyncMock(return_value=[]), graph_store=env.graph_store, memory_store=env.memory_store,
        )
        return env.loop_store.record_corroboration

    assert (await run(LoopState.ACTIVE, [_ref()])).await_count == 1
    assert (await run(LoopState.ACTIVE, [])).await_count == 0
    assert (await run(LoopState.SUSPECTED, [_ref()])).await_count == 0
    assert (await run(LoopState.DRIFTING, [_ref()])).await_count == 0


A, B = _ref(), _ref()


@pytest.mark.parametrize(
    "dropped_evidence,new_evidence,suppressed",
    [([A], [A], True), ([A], [B], False), ([], [], True), ([], [B], False)],
)
async def test_dismissal_fingerprint_semantics(monkeypatch, dropped_evidence, new_evidence, suppressed):
    dropped = _loop(LoopState.DROPPED, fingerprint=compute_evidence_fingerprint(dropped_evidence))
    env = _Env(monkeypatch, {("dropped",): dropped})
    llm = AsyncMock()
    llm.complete = AsyncMock(
        return_value=json.dumps({"is_loop": True, "title": "Renew passport", "explicit_declaration": False})
    )
    result = await extraction.propose_loop_candidates(
        "maybe renew passport", "email", new_evidence, llm, AsyncMock(), env.loop_store,
        AsyncMock(return_value=[]), graph_store=env.graph_store, memory_store=env.memory_store,
    )
    assert (result == []) is suppressed


def _system_one_positive():
    class S1:
        async def evaluate(self, state, questions, *, max_attempts=None):
            return SystemOneResult(
                outcome="ok",
                answers={
                    "is_open_concern": SystemOneAnswer(type="noul", noul=0.9),
                    "resolves_existing": SystemOneAnswer(type="noul", noul=0.0),
                    "explicit_declaration": SystemOneAnswer(type="noul", noul=0.1),
                },
                latency_ms=1,
            )

    return S1()


def _inflow(monkeypatch):
    env = _Env(monkeypatch)
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=json.dumps({"title": "Renew passport"}))
    inflow = LoopInflow(
        loop_store=env.loop_store,
        graph_store=env.graph_store,
        entity_resolver=AsyncMock(return_value=[]),
        llm_client=llm,
        embedder=AsyncMock(),
        memory_store=env.memory_store,
        system_one_client=_system_one_positive(),
        settings={"system_one": {"surfaces": {"loop_gate": BARS}}},
    )
    return inflow, env


async def test_admission_commit_takes_evidence_and_links_it(monkeypatch):
    inflow, env = _inflow(monkeypatch)
    ref = _ref()
    admission = await conversation_admit(inflow, {}, prompt="Daniel is still waiting on my answer to the passport form")

    created = await admission.commit([ref])

    assert len(created) == 1
    env.loop_store.link_evidence.assert_awaited_once_with(created[0].id, "episode", ref.id)


async def test_extract_forwards_evidence_through_the_commit(monkeypatch):
    inflow, env = _inflow(monkeypatch)
    ref = _ref()

    await inflow.extract("Daniel is still waiting on my answer to the passport form", "email", evidence=[ref])

    env.loop_store.link_evidence.assert_awaited_once()
    assert env.loop_store.link_evidence.await_args.args[1:] == ("episode", ref.id)


async def test_extract_without_evidence_still_works(monkeypatch):
    inflow, env = _inflow(monkeypatch)
    await inflow.extract("Daniel is still waiting on my answer to the passport form", "calendar")
    env.loop_store.link_evidence.assert_not_awaited()
