from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import admission
from ze_worldstate.admission import LoopInflow
from ze_worldstate.decision import CommitDecision
from ze_worldstate.errors import InvalidLoopTransitionError
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.lifecycle import LoopDraft, LoopLifecycle
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop, SourceKey

BARS = {"enabled": True, "loop_hold": 0.5, "resolves_hold": 0.7}
EPISODE = EvidenceRef(kind="episode", id=uuid4())


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


def _loop(state=LoopState.SUSPECTED, **kw) -> OpenLoop:
    fields = dict(title="Renew passport", provenance="conversation", confidence=0.3)
    fields.update(kw, state=state)
    fields.setdefault("id", uuid4())
    return OpenLoop(**fields)


def _lifecycle() -> AsyncMock:
    lifecycle = AsyncMock(spec=LoopLifecycle)
    lifecycle.create_suspected.side_effect = lambda draft: _loop(
        title=draft.title, provenance=draft.provenance
    )
    lifecycle.create_declared.side_effect = lambda draft, window_days=None: _loop(
        LoopState.ACTIVE, title=draft.title, provenance=draft.provenance, confidence=0.9
    )
    lifecycle.resolve.side_effect = lambda loop_id, evidence: _loop(
        LoopState.CLOSED, id=loop_id
    )
    lifecycle.note_evidence.side_effect = lambda loop_id, evidence, entity_ids: _loop(
        id=loop_id
    )
    return lifecycle


def _stores():
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[])
    graph_store = AsyncMock()
    graph_store.list_relationships = AsyncMock(return_value=[])
    return loop_store, graph_store


def _inflow(system_one=None, llm=None, settings=None, **kw):
    loop_store, graph_store = _stores()
    lifecycle = _lifecycle()
    llm = llm or CountingLLM()
    inflow = LoopInflow(
        lifecycle=lifecycle,
        loop_store=loop_store,
        graph_store=graph_store,
        entity_resolver=AsyncMock(return_value=[]),
        llm_client=llm,
        embedder=AsyncMock(),
        system_one_client=system_one,
        settings=_settings() if settings is None else settings,
        **kw,
    )
    return inflow, lifecycle, llm


def _match(monkeypatch, *found):
    """find_matching_loop answers in call order: one value per lookup."""
    finder = AsyncMock(side_effect=list(found))
    monkeypatch.setattr(admission, "find_matching_loop", finder)
    return finder


def _decision(kind, **kw):
    return CommitDecision(kind, "test", **kw)


# --- the commit decision table --------------------------------------------------------


async def test_hold_writes_nothing():
    inflow, lifecycle, llm = _inflow()
    result = await inflow.commit(
        _decision("hold"), text="thanks!", inflow="conversation"
    )
    assert (result.outcome, result.loops) == ("held", ())
    assert llm.calls == []
    assert lifecycle.method_calls == []


async def test_fallback_runs_the_109_gate_once_and_commits_its_decision():
    llm = CountingLLM(gate={"is_loop": True, "title": "Send contract"})
    inflow, lifecycle, _ = _inflow(llm=llm)
    result = await inflow.commit(
        _decision("fallback"),
        text="Please send the contract",
        inflow="email",
        evidence=[EPISODE],
    )
    assert result.outcome == "created"
    assert sum("relevance gate" in s for s in llm.calls) == 1
    assert all("title of one open loop" not in s for s in llm.calls)
    draft = lifecycle.create_suspected.await_args.args[0]
    assert (draft.title, draft.provenance, draft.evidence) == (
        "Send contract",
        "email",
        (EPISODE,),
    )


async def test_fallback_gate_declaration_creates_declared_with_its_window():
    llm = CountingLLM(
        gate={
            "is_loop": True,
            "title": "Renew passport",
            "explicit_declaration": True,
            "implied_window_days": 3,
        }
    )
    inflow, lifecycle, _ = _inflow(llm=llm)
    result = await inflow.commit(
        _decision("fallback"), text="I need to renew my passport", inflow="conversation"
    )
    assert result.outcome == "created"
    (draft,), kw = (
        lifecycle.create_declared.await_args.args,
        lifecycle.create_declared.await_args.kwargs,
    )
    assert draft.provenance == LoopProvenance.USER_DECLARED
    assert kw == {"window_days": 3}


@pytest.mark.parametrize(
    "gate",
    [{"is_loop": False, "title": ""}, {"is_loop": True, "title": ""}],
)
async def test_fallback_gate_that_finds_no_loop_holds(gate):
    inflow, lifecycle, _ = _inflow(llm=CountingLLM(gate=gate))
    result = await inflow.commit(_decision("fallback"), text="thanks", inflow="email")
    assert result.outcome == "held"
    assert lifecycle.method_calls == []


async def test_fallback_gate_failure_holds():
    class Down:
        async def complete(self, messages, **kw):
            raise RuntimeError("down")

    inflow, lifecycle, _ = _inflow(llm=Down())
    result = await inflow.commit(_decision("fallback"), text="x", inflow="email")
    assert (result.outcome, result.reason) == ("held", "gate_failed")


@pytest.mark.parametrize("writer", [{"title": ""}, {"nope": 1}, "boom"])
@pytest.mark.parametrize("kind", ["create_declared", "create_suspected", "resolve"])
async def test_no_title_writes_nothing(kind, writer):
    inflow, lifecycle, _ = _inflow(llm=CountingLLM(writer=writer))
    result = await inflow.commit(
        _decision(kind), text="I need to renew my passport", inflow="conversation"
    )
    assert result.outcome == "no_title"
    assert lifecycle.method_calls == []


async def test_suspected_create_uses_writer_only():
    llm = CountingLLM(writer={"title": "Answer Daniel", "implied_window_days": 3})
    inflow, lifecycle, _ = _inflow(llm=llm)
    result = await inflow.commit(
        _decision("create_suspected"),
        text="Daniel is still waiting on my answer",
        inflow="conversation",
        evidence=[EPISODE],
        source=SourceKey("conversation", "t1"),
    )
    assert result.outcome == "created" and len(result.loops) == 1
    assert all("relevance gate" not in s for s in llm.calls)
    lifecycle.create_suspected.assert_awaited_once_with(
        LoopDraft(
            "Answer Daniel",
            "conversation",
            (EPISODE,),
            (),
            SourceKey("conversation", "t1"),
        )
    )
    lifecycle.create_declared.assert_not_called()


@pytest.mark.parametrize(
    "window,expected_days",
    [
        ({"implied_window_days": 3}, 3),
        ({}, None),
        ({"implied_window_days": -2}, None),
        ({"implied_window_days": 2.5}, None),
        ({"implied_window_days": "3"}, None),
        ({"implied_window_days": True}, None),
    ],
)
async def test_declared_create_passes_the_writers_window(window, expected_days):
    llm = CountingLLM(writer={"title": "Renew passport", **window})
    inflow, lifecycle, _ = _inflow(llm=llm)
    result = await inflow.commit(
        _decision("create_declared"),
        text="I need to renew my passport by Friday",
        inflow="conversation",
    )
    assert result.outcome == "created"
    draft = lifecycle.create_declared.await_args.args[0]
    assert draft.provenance == LoopProvenance.USER_DECLARED
    assert lifecycle.create_declared.await_args.kwargs == {"window_days": expected_days}


async def test_declared_provenance_outside_the_conversation_is_the_inflow_name():
    inflow, lifecycle, _ = _inflow()
    await inflow.commit(
        _decision("create_declared"), text="I must call the bank", inflow="email"
    )
    assert lifecycle.create_declared.await_args.args[0].provenance == "email"


async def test_decision_title_and_window_skip_the_writer():
    llm = CountingLLM()
    inflow, lifecycle, _ = _inflow(llm=llm)
    await inflow.commit(
        _decision("create_declared", title="Pay rent", window_days=2),
        text="pay rent",
        inflow="conversation",
    )
    assert llm.calls == []
    assert lifecycle.create_declared.await_args.args[0].title == "Pay rent"
    assert lifecycle.create_declared.await_args.kwargs == {"window_days": 2}


# --- resolve ----------------------------------------------------------------------------


async def test_resolve_closes_the_matching_loop(monkeypatch):
    existing = _loop(LoopState.ACTIVE)
    _match(monkeypatch, existing)
    inflow, lifecycle, _ = _inflow()
    result = await inflow.commit(
        _decision("resolve"),
        text="I renewed my passport, it is done",
        inflow="conversation",
        evidence=[EPISODE],
    )
    assert result.outcome == "resolved"
    assert result.loops[0].state is LoopState.CLOSED
    lifecycle.resolve.assert_awaited_once_with(existing.id, evidence=(EPISODE,))
    lifecycle.create_suspected.assert_not_called()
    lifecycle.create_declared.assert_not_called()


async def test_resolve_without_a_live_match_is_no_match_not_an_error(monkeypatch):
    _match(monkeypatch, None)
    inflow, lifecycle, _ = _inflow()
    result = await inflow.commit(
        _decision("resolve"), text="I renewed my passport", inflow="conversation"
    )
    assert result.outcome == "no_match"
    lifecycle.resolve.assert_not_called()


async def test_resolve_that_races_to_a_terminal_loop_is_no_match(monkeypatch):
    _match(monkeypatch, _loop(LoopState.ACTIVE))
    inflow, lifecycle, _ = _inflow()
    lifecycle.resolve.side_effect = None
    lifecycle.resolve.return_value = None
    result = await inflow.commit(
        _decision("resolve"), text="done", inflow="conversation"
    )
    assert result.outcome == "no_match"


# --- the match flow ---------------------------------------------------------------------


async def test_suspected_create_blocked_by_a_dismissed_fingerprint(monkeypatch):
    dropped = _loop(
        LoopState.DROPPED,
        dismissed_evidence_fingerprint=compute_evidence_fingerprint([EPISODE]),
    )
    _match(monkeypatch, dropped)
    inflow, lifecycle, _ = _inflow()
    result = await inflow.commit(
        _decision("create_suspected"),
        text="renew passport",
        inflow="conversation",
        evidence=[EPISODE],
    )
    assert result.outcome == "dismissed"
    assert lifecycle.method_calls == []


async def test_different_evidence_is_not_dismissed(monkeypatch):
    dropped = _loop(
        LoopState.DROPPED,
        dismissed_evidence_fingerprint=compute_evidence_fingerprint([EPISODE]),
    )
    _match(monkeypatch, dropped, None)
    inflow, lifecycle, _ = _inflow()
    other = EvidenceRef(kind="episode", id=uuid4())
    result = await inflow.commit(
        _decision("create_suspected"),
        text="renew passport",
        inflow="conversation",
        evidence=[other],
    )
    assert result.outcome == "created"


@pytest.mark.parametrize("kind", ["create_suspected", "create_declared"])
async def test_a_live_non_suspected_match_notes_the_evidence(monkeypatch, kind):
    existing = _loop(LoopState.ACTIVE)
    _match(monkeypatch, *([None] if kind == "create_suspected" else []), existing)
    inflow, lifecycle, _ = _inflow()
    result = await inflow.commit(
        _decision(kind), text="renew passport", inflow="email", evidence=[EPISODE]
    )
    assert result.outcome == "matched"
    lifecycle.note_evidence.assert_awaited_once_with(
        existing.id, evidence=(EPISODE,), entity_ids=()
    )
    lifecycle.create_suspected.assert_not_called()
    lifecycle.create_declared.assert_not_called()


async def test_a_suspected_match_goes_to_the_corroborator(monkeypatch):
    existing = _loop(LoopState.SUSPECTED)
    _match(monkeypatch, None, existing)
    inflow, lifecycle, _ = _inflow()
    seen = []

    async def on_match(loop, dropped, match):
        seen.append((loop, dropped, match))
        return _loop(LoopState.SUSPECTED, id=loop.id, confidence=0.45)

    inflow._corroborator.on_suspected_match = on_match
    result = await inflow.commit(
        _decision("create_suspected"),
        text="renew passport",
        inflow="email",
        evidence=[EPISODE],
        source=SourceKey("email", "m1"),
    )
    assert result.outcome == "matched" and result.loops[0].confidence == 0.45
    [(loop, dropped, match)] = seen
    assert (loop, dropped) == (existing, None)
    assert (match.inflow, match.key, match.evidence) == (
        "email",
        SourceKey("email", "m1"),
        (EPISODE,),
    )


async def test_a_declared_create_that_matches_a_suspected_loop_passes_the_dropped_loop(
    monkeypatch,
):
    existing, dropped = _loop(LoopState.SUSPECTED), _loop(LoopState.DROPPED)
    _match(monkeypatch, existing, dropped)
    inflow, _, _ = _inflow()
    seen = []

    async def on_match(loop, dropped_loop, match):
        seen.append(dropped_loop)
        return loop

    inflow._corroborator.on_suspected_match = on_match
    await inflow.commit(
        _decision("create_declared"), text="renew passport", inflow="conversation"
    )
    assert seen == [dropped]


# --- never raises -----------------------------------------------------------------------


async def test_a_lifecycle_error_is_an_error_result_never_raised(monkeypatch):
    inflow, lifecycle, _ = _inflow()
    lifecycle.create_suspected.side_effect = InvalidLoopTransitionError("nope")
    result = await inflow.commit(
        _decision("create_suspected"), text="renew passport", inflow="email"
    )
    assert result.outcome == "error" and result.loops == ()


async def test_a_declared_create_with_unknown_evidence_is_an_error_and_no_loop():
    inflow, lifecycle, _ = _inflow()
    lifecycle.create_declared.side_effect = RuntimeError("evidence episode not found")
    result = await inflow.commit(
        _decision("create_declared"),
        text="I need to renew my passport",
        inflow="conversation",
        evidence=[EPISODE],
    )
    assert result.outcome == "error"
    assert result.loops == ()


async def test_a_commit_failure_is_logged_once(monkeypatch):
    events = []
    monkeypatch.setattr(
        admission.log, "warning", lambda event, **kw: events.append(event)
    )
    inflow, lifecycle, _ = _inflow()
    lifecycle.create_suspected.side_effect = RuntimeError("boom")
    await inflow.commit(_decision("create_suspected"), text="x", inflow="email")
    assert events == ["loop_commit_failed"]


# --- SC-003: the commit path stays narrow -----------------------------------------------

_WORLDSTATE = Path(admission.__file__).parent
_COMMIT_PATH = {
    "admission.py": [
        "commit",
        "_commit",
        "_write_title",
        "_match",
        "_resolve",
        "_create_suspected",
        "_create_declared",
        "_draft",
        "_on_match",
    ],
    "extraction.py": [
        "decide_with_109_gate",
        "_run_extraction_gate",
        "write_loop_title",
        "resolve_entities",
    ],
    "corroboration.py": [
        "on_suspected_match",
        "_corroborate",
        "_judge",
        "is_independent",
        "corroborated_confidence",
    ],
}


def test_commit_path_arity():
    for filename, names in _COMMIT_PATH.items():
        tree = ast.parse((_WORLDSTATE / filename).read_text())
        defs = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for name in names:
            assert name in defs, f"{filename}: {name} is gone; update the list"
            args = defs[name].args
            count = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
            count -= 1 if args.args and args.args[0].arg == "self" else 0
            assert count <= 8, f"{filename}:{name} takes {count} parameters"


def test_the_deleted_commit_machinery_is_gone():
    assert not hasattr(LoopInflow, "commit_for")
    from ze_worldstate import extraction

    for name in (
        "propose_loop_candidates",
        "_commit_admitted",
        "_create_declared_loop",
        "_create_suspected_loop",
        "_close_matching_loop",
        "_match_existing",
        "_corroborate_match",
        "_record_origin",
        "_link_evidence_and_entities",
    ):
        assert not hasattr(extraction, name), name


def test_finish_builds_the_full_record_and_attaches_nothing_callable():
    inflow, _, _ = _inflow()
    source = SourceKey("conversation", "t1")
    adm = inflow.finish(
        "hello", "conversation", _decision("create_suspected"), source=source
    )
    assert (adm.text, adm.inflow, adm.source) == ("hello", "conversation", source)
    assert adm.commit is None


# --- email, calendar and ingestion: judge, log, commit ---------------------------------


@pytest.mark.parametrize(
    "prov,state_key",
    [("email", "email"), ("calendar", "event"), ("ingestion", "facts")],
)
async def test_other_inflows_judge_with_own_shape_and_create_suspected(prov, state_key):
    client = FakeSystemOne(_ok(concern=0.9))
    inflow, lifecycle, llm = _inflow(client)
    await inflow.extract("Please send the contract by Friday " * 100, prov)
    state, questions, attempts = client.calls[0]
    assert state["source"] == prov and state_key in state
    assert "explicit_declaration" not in questions
    (draft,) = [c.args[0] for c in lifecycle.create_suspected.await_args_list]
    assert draft.provenance == prov
    assert all("relevance gate" not in s for s in llm.calls)


async def test_other_inflow_negative_makes_no_haiku_call():
    client = FakeSystemOne(_ok(concern=0.0))
    inflow, lifecycle, llm = _inflow(client)
    await inflow.extract("50% off everything, ends tonight", "email")
    assert llm.calls == []
    lifecycle.create_suspected.assert_not_called()


async def test_other_inflow_logs_judgment(monkeypatch):
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
    inflow, lifecycle, _ = _inflow(None, llm)
    await inflow.extract("Please send the contract", "email")
    assert any("relevance gate" in s for s in llm.calls)
    lifecycle.create_suspected.assert_awaited_once()


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


async def test_extract_commits_with_the_source_key():
    inflow, lifecycle, _ = _inflow(FakeSystemOne(_ok(concern=0.9)))
    await inflow.extract(
        "Please send the contract", "email", evidence=[EPISODE], source_ref="m1"
    )
    draft = lifecycle.create_suspected.await_args.args[0]
    assert draft.source == SourceKey("email", "m1")
    assert draft.evidence == (EPISODE,)
