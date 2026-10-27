"""CommitmentIntake.admit — one request, outcome handling, fallbacks, links (phase 173)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ze_agents.system_one import SystemOneResult
from ze_agents.types import ToolCall
from ze_plugin.contribution import EvidenceRef

from tests.commitment_fixtures import _BARS, commit_loop, make
from ze_worldstate import admission as admission_mod
from ze_worldstate import intake as intake_mod
from ze_worldstate.admission import LoopInflow
from ze_worldstate.commitment_judge import COMMITMENT_QUESTIONS, build_state
from ze_worldstate.intake import CommitmentIntake
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop, SourceKey

SETTINGS = {
    "system_one": {"surfaces": {"commitment_intake": {"enabled": True, **_BARS}}}
}
PROMPT = "I need to renew my passport before the trip"


class FakeSystemOne:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.calls = result, exc, []

    async def evaluate(self, state, questions, *, max_attempts=None):
        self.calls.append((state, questions, max_attempts))
        if self.exc:
            raise self.exc
        return self.result


class FakeLLM:
    """Routes by system prompt: fact value writer, Haiku fact judge, loop gate, title writer."""

    def __init__(
        self, *, gate=None, title="Renew passport", fact_value="prefers aisle seats"
    ):
        self.calls: list[str] = []
        self.gate = gate or {"is_loop": False, "title": ""}
        self.title = title
        self.fact_value = fact_value
        self.fact_exc: Exception | None = None

    async def complete(self, messages, **kw):
        system = kw.get("system", "")
        self.calls.append(system)
        if "relevance gate" in system:
            return json.dumps(self.gate)
        if "admission gate for durable facts" in system:
            return json.dumps(
                {
                    "speech_act": "fact",
                    "family": "preference",
                    "facts": [{"value": "haiku aisle"}],
                }
            )
        if "You phrase one durable fact" in system:
            if self.fact_exc:
                raise self.fact_exc
            return json.dumps({"facts": [{"value": self.fact_value}]})
        return json.dumps({"title": self.title})


def _stored(draft, state, confidence):
    return OpenLoop(
        title=draft.title,
        provenance=draft.provenance,
        confidence=confidence,
        state=state,
        id=uuid4(),
    )


def _lifecycle():
    lifecycle = AsyncMock(spec=LoopLifecycle)
    lifecycle.create_suspected.side_effect = lambda draft: _stored(
        draft, LoopState.SUSPECTED, 0.3
    )
    lifecycle.create_declared.side_effect = lambda draft, window_days=None: _stored(
        draft, LoopState.ACTIVE, 0.9
    )
    lifecycle.resolve.side_effect = lambda loop_id, evidence: OpenLoop(
        title="x",
        provenance="conversation",
        confidence=0.3,
        state=LoopState.CLOSED,
        id=loop_id,
    )
    lifecycle.link.return_value = True
    return lifecycle


def _build(system_one=None, llm=None, settings=SETTINGS):
    llm = llm or FakeLLM()
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[])
    lifecycle = _lifecycle()
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[])
    resolver = AsyncMock(return_value=[])
    embedder = AsyncMock()
    inflow = LoopInflow(
        lifecycle=lifecycle,
        loop_store=loop_store,
        graph_store=graph_store,
        entity_resolver=resolver,
        llm_client=llm,
        embedder=embedder,
        system_one_client=system_one,
        settings=settings,
    )
    intake = CommitmentIntake(
        loop_inflow=inflow,
        lifecycle=lifecycle,
        loop_store=loop_store,
        graph_store=graph_store,
        entity_resolver=resolver,
        embedder=embedder,
        system_one_client=system_one,
        settings=settings,
    )
    return intake, lifecycle, llm


def _no_creates(lifecycle):
    lifecycle.create_suspected.assert_not_called()
    lifecycle.create_declared.assert_not_called()


def _configurable(llm, settings=SETTINGS, thread_id="t1"):
    return {"openrouter_client": llm, "settings": settings, "thread_id": thread_id}


async def _admit(
    intake, llm, *, prompt=PROMPT, response="Noted.", tool_calls=None, **kw
):
    return await intake.admit(
        _configurable(llm, **kw),
        prompt=prompt,
        response=response,
        agent="companion",
        tool_calls=tool_calls,
    )


def _tc(name, result, success=True):
    return ToolCall(
        tool_name=name, args={}, result=result, duration_ms=1, success=success
    )


_REMINDER = [_tc("set_reminder", {"id": str(uuid4()), "label": "call Ana"})]
_GOAL = [_tc("create_goal", {"id": str(uuid4()), "title": "MVP"})]


# ── one request (US7) ────────────────────────────────────────────────────────


async def test_exactly_one_request_with_single_attempt_and_all_questions():
    client = FakeSystemOne(make("none"))
    intake, _, llm = _build(client)
    adm = await _admit(intake, llm)
    assert len(client.calls) == 1
    state, questions, attempts = client.calls[0]
    assert attempts == 1
    assert questions is COMMITMENT_QUESTIONS
    assert state == build_state(PROMPT, "Noted.")
    assert adm.question_ids == tuple(COMMITMENT_QUESTIONS)
    assert adm.judgment is not None


@pytest.mark.parametrize("prompt", ["thanks!", "ok", ""])
async def test_trivial_turn_makes_no_request(prompt):
    client = FakeSystemOne(make("loop"))
    intake, _, llm = _build(client)
    adm = await _admit(intake, llm, prompt=prompt)
    assert client.calls == []
    assert adm.outcome.reason == "trivial"
    assert adm.loop is not None and adm.loop.decision.kind == "hold"
    assert adm.fact is None
    assert llm.calls == []


# ── fallbacks run today's Haiku paths ────────────────────────────────────────

_FALLBACKS = [
    ("off", {}, FakeSystemOne(make("loop"))),
    (
        "disabled",
        {
            "system_one": {
                "surfaces": {"commitment_intake": {**_BARS, "enabled": False}}
            }
        },
        FakeSystemOne(make("loop")),
    ),
    (
        "uncalibrated",
        {
            "system_one": {
                "surfaces": {
                    "commitment_intake": {
                        "enabled": True,
                        **{**_BARS, "loop_hold": None},
                    }
                }
            }
        },
        FakeSystemOne(make("loop")),
    ),
    ("no_client", SETTINGS, None),
    (
        "skip",
        SETTINGS,
        FakeSystemOne(SystemOneResult(outcome="skip", skip_reason="timeout")),
    ),
    ("throw", SETTINGS, FakeSystemOne(exc=RuntimeError("down"))),
    (
        "invalid",
        SETTINGS,
        FakeSystemOne(SystemOneResult(outcome="ok", answers={})),
    ),
]


@pytest.mark.parametrize(
    ("name", "settings", "client"), _FALLBACKS, ids=[f[0] for f in _FALLBACKS]
)
async def test_fallback_runs_haiku_fact_and_109_loop_gate(name, settings, client):
    llm = FakeLLM(gate={"is_loop": True, "title": "Renew passport"})
    intake, lifecycle, _ = _build(client, llm, settings)
    adm = await _admit(intake, llm, settings=settings)
    assert adm.outcome.kind == "fallback"
    assert adm.fact is not None and adm.fact.path == "haiku"
    assert [f.value for f in adm.fact.facts] == ["haiku aisle"]
    assert adm.loop is not None and adm.loop.decision.kind == "fallback"
    result = await commit_loop(intake.loop_inflow, adm.loop)
    created = result.loops
    assert [loop.title for loop in created] == ["Renew passport"]
    assert created[0].state == LoopState.SUSPECTED
    assert any("relevance gate" in s for s in llm.calls)
    if client is not None and name in {"off", "disabled", "uncalibrated"}:
        assert client.calls == []


async def test_failing_fallback_requests_still_return_a_judgment_for_the_trace():
    client = FakeSystemOne(SystemOneResult(outcome="skip", skip_reason="timeout"))
    intake, _, llm = _build(client)
    adm = await _admit(intake, llm)
    assert adm.skip_reason == "timeout"
    assert adm.judgment is client.result
    assert set(adm.question_kinds) == set(COMMITMENT_QUESTIONS)


async def test_fallback_skips_loop_gate_when_track_loop_succeeded():
    client = FakeSystemOne(exc=RuntimeError("down"))
    intake, _, llm = _build(client)
    adm = await _admit(intake, llm, tool_calls=[_tc("track_loop", {"ok": True})])
    assert adm.loop is None
    assert adm.fact is not None


@pytest.mark.parametrize("calls", [_REMINDER, _GOAL], ids=["reminder", "goal"])
async def test_fallback_skips_loop_gate_when_turn_created_reminder_or_goal(calls):
    intake, lifecycle, llm = _build(FakeSystemOne(exc=RuntimeError("down")))
    adm = await _admit(intake, llm, tool_calls=calls)
    assert adm.loop is None
    assert adm.fact is not None
    _no_creates(lifecycle)
    assert not any("relevance gate" in s for s in llm.calls)


async def test_fact_fallback_error_never_raises(monkeypatch):
    monkeypatch.setattr(
        intake_mod, "gather_fact_proposals", AsyncMock(side_effect=RuntimeError("x"))
    )
    intake, _, llm = _build(FakeSystemOne(exc=RuntimeError("down")))
    adm = await _admit(intake, llm)
    assert adm.fact.path == "none"


# ── loop outcomes (US4, parity with 168) ─────────────────────────────────────


async def test_declared_creates_active_loop_with_writer_only():
    llm = FakeLLM(title="Renew passport")
    intake, lifecycle, _ = _build(FakeSystemOne(make("loop", explicit=0.95)), llm)
    adm = await _admit(intake, llm)
    assert adm.outcome.kind == "create_declared"
    assert adm.fact is None and not adm.links
    assert adm.loop.source == SourceKey("conversation", "t1")
    result = await commit_loop(intake.loop_inflow, adm.loop)
    (created,) = result.loops
    assert created.state == LoopState.ACTIVE and created.confidence == 0.9
    assert created.provenance == LoopProvenance.USER_DECLARED
    assert all("relevance gate" not in s for s in llm.calls)
    draft = lifecycle.create_declared.await_args.args[0]
    assert draft.source == SourceKey("conversation", "t1")


async def test_suspected_creates_suspected_loop():
    llm = FakeLLM()
    intake, _, _ = _build(FakeSystemOne(make("loop", explicit=0.1)), llm)
    adm = await _admit(intake, llm)
    assert adm.outcome.kind == "create_suspected"
    result = await commit_loop(intake.loop_inflow, adm.loop)
    (created,) = result.loops
    assert created.state == LoopState.SUSPECTED and created.confidence == 0.3


async def test_resolve_closes_matching_loop(monkeypatch):
    existing = OpenLoop(
        title="x",
        provenance="conversation",
        confidence=0.3,
        state=LoopState.ACTIVE,
        id=uuid4(),
    )
    monkeypatch.setattr(
        admission_mod, "find_matching_loop", AsyncMock(return_value=existing)
    )
    llm = FakeLLM()
    intake, lifecycle, _ = _build(FakeSystemOne(make("none", resolves=0.95)), llm)
    adm = await _admit(intake, llm, prompt="I renewed my passport, it is done")
    assert adm.outcome.kind == "resolve"
    assert adm.loop.decision.kind == "resolve"
    assert adm.consumed == frozenset({"resolves_existing"})
    evidence = [EvidenceRef(kind="episode", id=uuid4())]
    result = await commit_loop(intake.loop_inflow, adm.loop, evidence)
    assert result.outcome == "resolved"
    lifecycle.resolve.assert_awaited_once_with(existing.id, evidence=tuple(evidence))
    _no_creates(lifecycle)


async def test_tracked_turn_creates_no_loop_but_still_decides_facts():
    client = FakeSystemOne(make("loop"))
    intake, lifecycle, llm = _build(client)
    adm = await _admit(intake, llm, tool_calls=[_tc("track_loop", {"ok": True})])
    assert (adm.outcome.kind, adm.outcome.reason) == ("hold", "tracked")
    assert adm.loop is None
    _no_creates(lifecycle)


async def test_hold_has_no_commit_and_no_writes():
    intake, lifecycle, llm = _build(FakeSystemOne(make("loop", concern=0.1)))
    adm = await _admit(intake, llm)
    assert adm.outcome.kind == "hold"
    assert adm.loop is None and adm.fact is None and not adm.links
    _no_creates(lifecycle)
    assert llm.calls == []


async def test_waiting_on_creates_nothing():
    intake, lifecycle, llm = _build(FakeSystemOne(make("waiting_on")))
    adm = await _admit(intake, llm, prompt="My landlord said he would get back to me")
    assert (adm.outcome.kind, adm.outcome.reason) == ("hold", "waiting_on")
    assert adm.loop is None and adm.fact is None and not adm.links
    _no_creates(lifecycle)
    lifecycle.link.assert_not_called()
    assert llm.calls == []


# ── facts (US6) ──────────────────────────────────────────────────────────────


async def test_persist_uses_value_writer_with_chosen_family():
    llm = FakeLLM()
    intake, _, _ = _build(FakeSystemOne(make("fact", family="preference")), llm)
    adm = await _admit(intake, llm, prompt="I prefer aisle seats")
    assert adm.outcome.kind == "persist_fact"
    assert adm.fact.path == "system_one"
    assert [(f.predicate, f.value, f.confidence, f.agent) for f in adm.fact.facts] == [
        ("preference", "prefers aisle seats", 0.8, "companion")
    ]
    assert not any("admission gate" in s for s in llm.calls)
    assert adm.loop is None


async def test_value_writer_failure_persists_nothing_without_fallback():
    llm = FakeLLM()
    llm.fact_exc = RuntimeError("boom")
    intake, _, _ = _build(FakeSystemOne(make("fact")), llm)
    adm = await _admit(intake, llm, prompt="I prefer aisle seats")
    assert adm.fact.facts == []
    assert len([s for s in llm.calls if "phrase one durable fact" in s]) == 1


@pytest.mark.parametrize("choice", ["forget", "ingest", "clarify", "none"])
async def test_non_fact_choices_write_nothing(choice):
    llm = FakeLLM()
    intake, lifecycle, _ = _build(FakeSystemOne(make(choice)), llm)
    adm = await _admit(intake, llm)
    assert adm.outcome.reason == choice
    assert adm.fact is None and adm.loop is None
    assert llm.calls == []


# ── turn-created reminder or goal (US1-US3) ──────────────────────────────────


@pytest.mark.parametrize("choice", ["reminder", "loop", "goal", "fact"])
@pytest.mark.parametrize("calls", [_REMINDER, _GOAL], ids=["reminder", "goal"])
async def test_turn_created_makes_no_loop_no_fact_and_no_haiku(choice, calls):
    llm = FakeLLM()
    intake, lifecycle, _ = _build(FakeSystemOne(make(choice, explicit=0.96)), llm)
    adm = await _admit(intake, llm, tool_calls=calls)
    assert adm.outcome.kind == "link"
    assert adm.loop is None and adm.fact is None
    _no_creates(lifecycle)
    assert llm.calls == []


@pytest.mark.parametrize("choice", ["reminder", "goal"])
async def test_choice_without_creation_holds_and_creates_no_loop(choice):
    intake, lifecycle, llm = _build(
        FakeSystemOne(make(choice, concern=0.95, explicit=0.96))
    )
    adm = await _admit(intake, llm)
    assert adm.outcome.reason == f"{choice}_not_created"
    assert adm.loop is None
    _no_creates(lifecycle)


async def test_parked_or_failed_creation_does_not_count():
    failed = [_tc("set_reminder", {"id": "r"}, success=False)]
    intake, _, llm = _build(FakeSystemOne(make("reminder")))
    adm = await _admit(intake, llm, tool_calls=failed)
    assert adm.outcome.reason == "reminder_not_created"


# ── linking (US2) ────────────────────────────────────────────────────────────


def _live(**kw):
    return SimpleNamespace(
        id=uuid4(), state=LoopState.ACTIVE, reminder_id=None, goal_id=None, **kw
    )


async def test_link_sets_reminder_pointer_once(monkeypatch):
    loop = _live()
    finder = AsyncMock(return_value=loop)
    monkeypatch.setattr(intake_mod, "find_matching_loop", finder)
    intake, lifecycle, llm = _build(FakeSystemOne(make("reminder")))
    rid = uuid4()
    adm = await _admit(intake, llm, tool_calls=[_tc("set_reminder", {"id": str(rid)})])
    lifecycle.link.assert_awaited_once_with(loop.id, reminder_id=rid)
    assert (adm.links[0].kind, adm.links[0].linked, adm.links[0].loop_id) == (
        "reminder",
        True,
        loop.id,
    )
    assert finder.await_args.kwargs["states"] == ["suspected", "active", "drifting"]
    assert finder.await_args.kwargs["verify_similarity"] is True
    assert finder.await_args.args[1] == PROMPT[:200]
    _no_creates(lifecycle)


async def test_link_sets_goal_pointer(monkeypatch):
    loop = _live()
    monkeypatch.setattr(intake_mod, "find_matching_loop", AsyncMock(return_value=loop))
    intake, lifecycle, llm = _build(FakeSystemOne(make("goal")))
    gid = uuid4()
    adm = await _admit(intake, llm, tool_calls=[_tc("create_goal", {"id": str(gid)})])
    lifecycle.link.assert_awaited_once_with(loop.id, goal_id=gid)
    assert adm.links[0].kind == "goal" and adm.links[0].linked


async def test_turn_creating_reminder_and_goal_links_both(monkeypatch):
    loop = _live()
    finder = AsyncMock(return_value=loop)
    monkeypatch.setattr(intake_mod, "find_matching_loop", finder)
    intake, lifecycle, llm = _build(FakeSystemOne(make("reminder")))
    rid, gid = uuid4(), uuid4()
    adm = await _admit(
        intake,
        llm,
        tool_calls=[
            _tc("set_reminder", {"id": str(rid)}),
            _tc("create_goal", {"id": str(gid)}),
        ],
    )
    assert [(link.kind, link.linked) for link in adm.links] == [
        ("reminder", True),
        ("goal", True),
    ]
    assert [c.kwargs for c in lifecycle.link.await_args_list] == [
        {"reminder_id": rid},
        {"goal_id": gid},
    ]
    _no_creates(lifecycle)


@pytest.mark.parametrize(
    ("loop", "reason"),
    [
        (
            SimpleNamespace(id=uuid4(), reminder_id=uuid4(), goal_id=None),
            "already_linked",
        ),
        (None, "no_match"),
    ],
)
async def test_link_never_overwrites_and_skips_without_match(monkeypatch, loop, reason):
    monkeypatch.setattr(intake_mod, "find_matching_loop", AsyncMock(return_value=loop))
    intake, lifecycle, llm = _build(FakeSystemOne(make("reminder")))
    adm = await _admit(
        intake, llm, tool_calls=[_tc("set_reminder", {"id": str(uuid4())})]
    )
    assert (adm.links[0].linked, adm.links[0].reason) == (False, reason)
    lifecycle.link.assert_not_called()


async def test_link_terminal_loop_is_refused_by_store(monkeypatch):
    monkeypatch.setattr(
        intake_mod, "find_matching_loop", AsyncMock(return_value=_live())
    )
    intake, lifecycle, llm = _build(FakeSystemOne(make("reminder")))
    lifecycle.link.return_value = False
    adm = await _admit(
        intake, llm, tool_calls=[_tc("set_reminder", {"id": str(uuid4())})]
    )
    assert (adm.links[0].linked, adm.links[0].reason) == (False, "unchanged")


async def test_link_non_uuid_id_is_skipped(monkeypatch):
    finder = AsyncMock()
    monkeypatch.setattr(intake_mod, "find_matching_loop", finder)
    intake, lifecycle, llm = _build(FakeSystemOne(make("reminder")))
    adm = await _admit(
        intake, llm, tool_calls=[_tc("set_reminder", {"id": "not-a-uuid"})]
    )
    assert adm.links[0].reason == "no_id"
    finder.assert_not_called()
    lifecycle.link.assert_not_called()


async def test_link_store_error_never_raises(monkeypatch):
    monkeypatch.setattr(
        intake_mod, "find_matching_loop", AsyncMock(return_value=_live())
    )
    intake, lifecycle, llm = _build(FakeSystemOne(make("reminder")))
    lifecycle.link.side_effect = RuntimeError("db")
    adm = await _admit(
        intake, llm, tool_calls=[_tc("set_reminder", {"id": str(uuid4())})]
    )
    assert (adm.links[0].linked, adm.links[0].reason) == (False, "error")


# ── the commit contract (phase 203) ──────────────────────────────────────────


async def test_loop_inflow_is_exposed_read_only():
    intake, _, _ = _build(FakeSystemOne(make("none")))
    assert isinstance(intake.loop_inflow, LoopInflow)
    with pytest.raises(AttributeError):
        intake.loop_inflow = None


@pytest.mark.parametrize(
    ("choice", "kwargs", "kind"),
    [
        ("loop", {"explicit": 0.95}, "create_declared"),
        ("loop", {"explicit": 0.1}, "create_suspected"),
        ("none", {"resolves": 0.95}, "resolve"),
    ],
)
async def test_the_loop_admission_is_a_full_commit_decision(choice, kwargs, kind):
    llm = FakeLLM()
    intake, _, _ = _build(FakeSystemOne(make(choice, **kwargs)), llm)
    adm = await _admit(intake, llm)
    loop = adm.loop
    assert (loop.decision.kind, loop.decision.reason) == (kind, adm.outcome.reason)
    assert loop.decision.consumed == adm.outcome.consumed
    assert (loop.text, loop.inflow) == (PROMPT, "conversation")
    assert loop.source == SourceKey("conversation", "t1")
    assert not hasattr(loop, "commit")


async def test_the_source_is_set_at_construction_and_absent_without_a_thread():
    llm = FakeLLM()
    intake, _, _ = _build(FakeSystemOne(make("loop", explicit=0.1)), llm)
    adm = await intake.admit(
        {"openrouter_client": llm, "settings": SETTINGS},
        prompt=PROMPT,
        response="",
        agent="companion",
    )
    assert adm.loop.source is None
