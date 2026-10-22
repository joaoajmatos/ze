from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult

from ze_worldstate.admission import LoopInflow
from ze_worldstate.loop_judge import LoopGateDecision
from ze_worldstate.types import LoopProvenance, LoopState

BARS = {"enabled": True, "loop_hold": 0.5, "resolves_hold": 0.7}


@pytest.fixture(autouse=True)
def _bypass_evidence_check(monkeypatch):
    """The seam rejects evidence-less suspicions (true of the 109 path too); these tests are about the gate."""
    from ze_worldstate import extraction

    async def submit(contribution, write, **kw):
        return await write()

    monkeypatch.setattr(extraction, "submit_and_detect_collisions", submit)


def _settings(block=BARS):
    return {"system_one": {"surfaces": {"loop_gate": block}}}


class FakeSystemOne:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    async def evaluate(self, state, questions, *, max_attempts=None):
        self.calls.append((state, dict(questions), max_attempts))
        if self.exc:
            raise self.exc
        return self.result


def _ok(concern=0.0, resolves=0.0, explicit=None):
    answers = {
        "is_open_concern": SystemOneAnswer(type="noul", noul=concern),
        "resolves_existing": SystemOneAnswer(type="noul", noul=resolves),
    }
    if explicit is not None:
        answers["explicit_declaration"] = SystemOneAnswer(type="noul", noul=explicit)
    return SystemOneResult(outcome="ok", answers=answers, latency_ms=5)


class CountingLLM:
    def __init__(self, gate=None, writer=None):
        self.calls = []
        self.gate = gate or {"is_loop": False, "title": ""}
        self.writer = writer or {"title": "Renew passport"}

    async def complete(self, messages, **kw):
        self.calls.append(kw.get("system", ""))
        if "relevance gate" in kw.get("system", ""):
            return json.dumps(self.gate)
        if self.writer == "boom":
            raise RuntimeError("down")
        return json.dumps(self.writer)


def _stores():
    loop_store = AsyncMock()
    loop_store.create = AsyncMock(side_effect=_with_id)
    loop_store.list = AsyncMock(return_value=[])
    loop_store.set_drift_deadline = AsyncMock()
    loop_store.transition = AsyncMock(side_effect=lambda i, st: _closed(i))
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[])
    return loop_store, graph_store


def _with_id(loop):
    loop.id = uuid4()
    return loop


def _closed(i):
    from ze_worldstate.types import OpenLoop

    return OpenLoop(
        title="x",
        provenance="conversation",
        confidence=0.3,
        state=LoopState.CLOSED,
        id=i,
    )


def _inflow(system_one=None, llm=None, settings=None, **kw):
    loop_store, graph_store = _stores()
    llm = llm or CountingLLM()
    inflow = LoopInflow(
        loop_store=loop_store,
        graph_store=graph_store,
        entity_resolver=AsyncMock(return_value=[]),
        llm_client=llm,
        embedder=AsyncMock(),
        system_one_client=system_one,
        settings=_settings() if settings is None else settings,
        **kw,
    )
    return inflow, loop_store, graph_store, llm


# --- US4: fallback keeps 109 behavior -------------------------------------------------


# --- US1: gate ------------------------------------------------------------------------


def _admitted(inflow, kind, text):
    """The commit the conversation intake builds once it has decided (173)."""
    consumed = {"resolve": {"resolves_existing"}}.get(kind, set())
    return inflow.finish(
        text, "conversation", LoopGateDecision(kind, "test", frozenset(consumed))
    )


# --- US2: writer and create -----------------------------------------------------------


async def test_suspected_create_uses_writer_only():
    llm = CountingLLM(writer={"title": "Answer Daniel", "implied_window_days": 3})
    inflow, loop_store, _, _ = _inflow(
        FakeSystemOne(_ok(concern=0.9, explicit=0.1)), llm
    )
    adm = _admitted(inflow, "create_suspected", "Daniel is still waiting on my answer")
    created = await adm.commit()
    assert len(created) == 1
    assert created[0].state == LoopState.SUSPECTED and created[0].confidence == 0.3
    assert created[0].provenance == "conversation"
    assert all("relevance gate" not in s for s in llm.calls)


@pytest.mark.parametrize(
    "window,expected_days",
    [
        ({"implied_window_days": 3}, 3),
        ({}, 7),
        ({"implied_window_days": -2}, 7),
        ({"implied_window_days": 2.5}, 7),
        ({"implied_window_days": "3"}, 7),
        ({"implied_window_days": True}, 7),
    ],
)
async def test_declared_create_window(window, expected_days):
    llm = CountingLLM(writer={"title": "Renew passport", **window})
    inflow, loop_store, _, _ = _inflow(
        FakeSystemOne(_ok(concern=0.9, explicit=0.95)), llm
    )
    adm = _admitted(inflow, "create_declared", "I need to renew my passport by Friday")
    assert adm.decision.kind == "create_declared"
    (created,) = await adm.commit()
    assert created.state == LoopState.ACTIVE and created.confidence == 0.9
    assert created.provenance == LoopProvenance.USER_DECLARED
    delta = created.drift_deadline - created.confirmed_at
    assert delta.days == expected_days


@pytest.mark.parametrize("writer", [{"title": ""}, {"nope": 1}, "boom"])
async def test_empty_title_or_writer_failure_creates_nothing(writer):
    llm = CountingLLM(writer=writer)
    inflow, loop_store, _, _ = _inflow(
        FakeSystemOne(_ok(concern=0.9, explicit=0.9)), llm
    )
    adm = _admitted(inflow, "create_declared", "I need to renew my passport")
    assert await adm.commit() == []
    loop_store.create.assert_not_called()


# --- US3: resolve ---------------------------------------------------------------------


async def test_resolves_closes_matching_loop(monkeypatch):
    from ze_worldstate import extraction

    existing = _closed(uuid4())
    monkeypatch.setattr(
        extraction, "find_matching_loop", AsyncMock(return_value=existing)
    )
    inflow, loop_store, _, llm = _inflow(
        FakeSystemOne(_ok(concern=0.9, resolves=0.9, explicit=0.9)),
        CountingLLM(writer={"title": "Renew passport"}),
    )
    adm = _admitted(inflow, "resolve", "I renewed my passport, it is done")
    assert adm.decision.kind == "resolve"
    assert adm.consumed == frozenset({"resolves_existing"})
    closed = await adm.commit()
    assert closed and closed[0].state == LoopState.CLOSED
    loop_store.transition.assert_awaited_once()
    loop_store.create.assert_not_called()


async def test_resolves_without_match_closes_and_creates_nothing(monkeypatch):
    from ze_worldstate import extraction

    monkeypatch.setattr(extraction, "find_matching_loop", AsyncMock(return_value=None))
    inflow, loop_store, _, _ = _inflow(
        FakeSystemOne(_ok(resolves=0.95, concern=0.1, explicit=0.0))
    )
    adm = _admitted(inflow, "resolve", "I renewed my passport, it is done")
    assert await adm.commit() == []
    loop_store.transition.assert_not_called()
    loop_store.create.assert_not_called()


# --- US5: other inflows log only ------------------------------------------------------


@pytest.mark.parametrize(
    "prov,state_key",
    [("email", "email"), ("calendar", "event"), ("ingestion", "facts")],
)
async def test_other_inflows_judge_with_own_shape_and_create_suspected(prov, state_key):
    client = FakeSystemOne(_ok(concern=0.9))
    inflow, loop_store, _, llm = _inflow(client)
    await inflow.extract("Please send the contract by Friday " * 100, prov)
    state, questions, attempts = client.calls[0]
    assert state["source"] == prov and state_key in state
    assert "explicit_declaration" not in questions
    (created,) = [c.args[0] for c in loop_store.create.await_args_list]
    assert created.state == LoopState.SUSPECTED and created.provenance == prov
    assert all("relevance gate" not in s for s in llm.calls)


async def test_other_inflow_negative_makes_no_haiku_call():
    client = FakeSystemOne(_ok(concern=0.0))
    inflow, loop_store, _, llm = _inflow(client)
    await inflow.extract("50% off everything, ends tonight", "email")
    assert llm.calls == []
    loop_store.create.assert_not_called()


async def test_other_inflow_logs_judgment(monkeypatch):
    from ze_worldstate import admission

    events = []
    monkeypatch.setattr(
        admission.log, "info", lambda event, **kw: events.append((event, kw))
    )
    inflow, *_ = _inflow(FakeSystemOne(_ok(concern=0.0)))
    await inflow.extract("50% off everything", "email")
    assert events and events[0][0] == "loop_gate_judgment"
    assert events[0][1]["provenance"] == "email"


async def test_other_inflow_missing_client_falls_back_to_haiku():
    llm = CountingLLM(gate={"is_loop": True, "title": "Send contract"})
    inflow, loop_store, _, _ = _inflow(None, llm)
    await inflow.extract("Please send the contract", "email")
    assert any("relevance gate" in s for s in llm.calls)
    loop_store.create.assert_awaited_once()


async def test_writer_accepts_fenced_json():
    class Fenced:
        async def complete(self, messages, **kw):
            return '```json\n{"title": "Renew passport", "implied_window_days": 4}\n```'

    from ze_worldstate.extraction import write_loop_title

    written = await write_loop_title(
        "I need to renew my passport", "create", Fenced(), "m"
    )
    assert written is not None
    assert (written.title, written.implied_window_days) == ("Renew passport", 4)
