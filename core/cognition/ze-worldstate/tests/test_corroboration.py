from __future__ import annotations

from uuid import uuid4

import pytest
from ze_plugin.contribution import EvidenceRef

from ze_worldstate.corroboration import (
    CORROBORATED_CAP,
    CORROBORATION_WEIGHT,
    PROMOTED_WINDOW_DAYS,
    corroborated_confidence,
    is_independent,
)
from ze_worldstate.lifecycle import DeclaredStamp
from ze_worldstate.lifecycle.rules import PROMOTED_CONFIDENCE
from ze_worldstate.types import LoopSource, LoopSourceRole, SourceKey


def _src(inflow: str, ref: str, role=LoopSourceRole.ORIGIN) -> LoopSource:
    return LoopSource(loop_id=uuid4(), role=role, key=SourceKey(inflow, ref))


# ---- independence ---------------------------------------------------------


def test_no_key_for_none_and_empty_ref():
    assert is_independent(None, [], [], [], []) == (False, "no_key")
    assert is_independent(SourceKey("email", ""), [], [], [], []) == (False, "no_key")


def test_same_source_as_origin():
    key = SourceKey("email", "T1")
    assert is_independent(key, [], [_src("email", "T1")], [], []) == (
        False,
        "same_source",
    )


def test_same_source_as_an_earlier_corroboration():
    key = SourceKey("email", "T2")
    sources = [
        _src("conversation", "c1"),
        _src("email", "T2", LoopSourceRole.CORROBORATION),
    ]
    assert is_independent(key, [], sources, [], []) == (False, "same_source")


def test_same_ref_in_another_inflow_is_independent():
    key = SourceKey("ingestion", "T1")
    assert is_independent(key, [], [_src("email", "T1")], [], []) == (
        True,
        "independent",
    )


def test_same_evidence():
    ref = EvidenceRef(kind="episode", id=uuid4())
    other = EvidenceRef(kind="episode", id=uuid4())
    key = SourceKey("email", "T9")
    assert is_independent(
        key, [other, ref], [_src("conversation", "c1")], [ref], []
    ) == (
        False,
        "same_evidence",
    )


def test_dropped_source():
    key = SourceKey("email", "G1")
    assert is_independent(
        key, [], [_src("conversation", "c1")], [], [_src("email", "G1")]
    ) == (False, "dropped_source")


def test_other_source_than_the_dropped_one_is_independent():
    key = SourceKey("email", "G2")
    assert is_independent(
        key, [], [_src("conversation", "c1")], [], [_src("email", "G1")]
    ) == (True, "independent")


def test_independent():
    key = SourceKey("email", "T1")
    new = EvidenceRef(kind="episode", id=uuid4())
    old = EvidenceRef(kind="episode", id=uuid4())
    assert is_independent(key, [new], [_src("conversation", "c1")], [old], []) == (
        True,
        "independent",
    )


def test_loop_without_origin_row_checks_corroboration_rows_and_evidence_only():
    key = SourceKey("email", "T1")
    corroboration = _src("calendar", "e1", LoopSourceRole.CORROBORATION)
    assert is_independent(key, [], [corroboration], [], []) == (True, "independent")
    assert is_independent(key, [], [], [], []) == (True, "independent")
    ref = EvidenceRef(kind="ingestion", id=uuid4())
    assert is_independent(key, [ref], [], [ref], []) == (False, "same_evidence")


# ---- constants and arithmetic ---------------------------------------------


def test_constants():
    assert (CORROBORATION_WEIGHT, CORROBORATED_CAP, PROMOTED_CONFIDENCE) == (
        0.5,
        0.6,
        0.7,
    )
    assert PROMOTED_WINDOW_DAYS == DeclaredStamp.DEFAULT_WINDOW_DAYS == 7


def test_corroborated_confidence_noisy_or():
    assert corroborated_confidence(0.3, 0.8) == pytest.approx(0.58)


def test_corroborated_confidence_is_capped():
    assert corroborated_confidence(0.58, 0.8) == CORROBORATED_CAP
    assert corroborated_confidence(0.6, 1.0) == CORROBORATED_CAP


def test_corroborated_confidence_never_lowers():
    assert corroborated_confidence(0.6, 0.0) == pytest.approx(0.6)
    assert corroborated_confidence(0.3, 0.0) == pytest.approx(0.3)


def test_higher_score_counts_more():
    assert corroborated_confidence(0.3, 0.98) > corroborated_confidence(0.3, 0.76)


# ---- effects --------------------------------------------------------------

from unittest.mock import AsyncMock  # noqa: E402

from structlog.testing import capture_logs  # noqa: E402
from ze_agents.system_one import SystemOneAnswer, SystemOneResult  # noqa: E402

from ze_worldstate.corroboration import Corroborator, MatchInput  # noqa: E402
from ze_worldstate.lifecycle import Corroboration, LoopLifecycle, SourceWrite  # noqa: E402
from ze_worldstate.types import LoopState, OpenLoop  # noqa: E402

BARS = {"enabled": True, "corroborate_hold": 0.6, "promote_hold": 0.85}
KEY = SourceKey("email", "T-new")


def _settings(block=BARS):
    return {"system_one": {"surfaces": {"corroboration": block}}}


class FakeSystemOne:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.calls = result, exc, []

    async def evaluate(self, state, questions, *, max_attempts=None):
        self.calls.append((state, dict(questions), max_attempts))
        if self.exc:
            raise self.exc
        return self.result


def _ok(score):
    return SystemOneResult(
        outcome="ok",
        model="test-model",
        latency_ms=42,
        answers={"same_concern": SystemOneAnswer(type="noul", noul=score)},
    )


def _loop(confidence=0.3, state=LoopState.SUSPECTED) -> OpenLoop:
    return OpenLoop(
        id=uuid4(),
        title="Reply to Ana about the budget",
        provenance="conversation",
        confidence=confidence,
        state=state,
    )


def _store(sources=None, evidence=None, dropped_sources=None):
    store = AsyncMock()
    store.owner = {}
    store.list_sources = AsyncMock(
        side_effect=lambda loop_id: list(
            (sources or [])
            if loop_id == store.owner.get("id")
            else (dropped_sources or [])
        )
    )
    store.list_evidence = AsyncMock(return_value=evidence or [])
    return store


def _lifecycle(outcome="corroborate"):
    lifecycle = AsyncMock(spec=LoopLifecycle)

    async def write(loop_id, corroboration):
        return SourceWrite(outcome, _loop())

    lifecycle.corroborate.side_effect = write
    lifecycle.promote.side_effect = write
    lifecycle.note_evidence.side_effect = lambda loop_id, evidence, entity_ids: _loop()
    return lifecycle


async def _run(
    existing,
    client,
    *,
    store=None,
    lifecycle=None,
    settings=None,
    dropped=None,
    evidence=None,
    text="Reminder: the budget reply to Ana is still pending.",
):
    store = store or _store()
    lifecycle = lifecycle or _lifecycle()
    store.owner["id"] = existing.id
    refs = tuple(evidence or [EvidenceRef(kind="episode", id=uuid4())])
    corroborator = Corroborator(
        lifecycle=lifecycle,
        loop_store=store,
        system_one_client=client,
        settings=_settings() if settings is None else settings,
    )
    result = await corroborator.on_suspected_match(
        existing, dropped, MatchInput(text, "email", KEY, refs, ())
    )
    return result, lifecycle, refs


def _events(logs, name):
    return [e for e in logs if e["event"] == name]


def _no_effect_but_note(lifecycle):
    lifecycle.corroborate.assert_not_awaited()
    lifecycle.promote.assert_not_awaited()
    lifecycle.note_evidence.assert_awaited_once()


async def test_corroborate_band_raises_confidence_through_one_lifecycle_call():
    existing = _loop(0.3)
    client = FakeSystemOne(_ok(0.8))
    with capture_logs() as logs:
        result, lifecycle, refs = await _run(existing, client)

    assert isinstance(result, SourceWrite) and result.outcome == "corroborate"
    lifecycle.corroborate.assert_awaited_once()
    loop_id, corroboration = lifecycle.corroborate.await_args.args
    assert loop_id == existing.id
    assert isinstance(corroboration, Corroboration)
    assert corroboration.confidence == pytest.approx(0.58)
    assert (
        corroboration.same_concern,
        corroboration.model,
        corroboration.latency_ms,
        corroboration.key,
        corroboration.evidence,
    ) == (0.8, "test-model", 42, KEY, refs)
    lifecycle.promote.assert_not_awaited()
    lifecycle.note_evidence.assert_not_awaited()
    assert len(client.calls) == 1 and client.calls[0][2] == 1
    [judgment] = _events(logs, "corroboration_judgment")
    assert judgment["outcome"] == "corroborate"
    assert judgment["loop_id"] == str(existing.id)
    for field in ("inflow", "reason", "score", "latency_ms", "skip_reason"):
        assert field in judgment


async def test_second_corroboration_is_capped():
    _, lifecycle, _ = await _run(_loop(0.58), FakeSystemOne(_ok(0.8)))
    corroboration = lifecycle.corroborate.await_args.args[1]
    assert corroboration.confidence == pytest.approx(0.6)


async def test_promote_is_one_lifecycle_call():
    existing = _loop(0.3)
    with capture_logs() as logs:
        result, lifecycle, _ = await _run(
            existing, FakeSystemOne(_ok(0.93)), lifecycle=_lifecycle("promote")
        )

    assert result.outcome == "promote"
    lifecycle.promote.assert_awaited_once()
    assert lifecycle.promote.await_args.args[0] == existing.id
    lifecycle.corroborate.assert_not_awaited()
    lifecycle.note_evidence.assert_not_awaited()
    assert _events(logs, "corroboration_judgment")[0]["outcome"] == "promote"


@pytest.mark.parametrize("outcome", ["lost_race", "duplicate_source"])
async def test_the_lifecycles_outcome_is_returned_and_logged(outcome):
    with capture_logs() as logs:
        result, lifecycle, _ = await _run(
            _loop(0.3), FakeSystemOne(_ok(0.93)), lifecycle=_lifecycle(outcome)
        )

    assert result.outcome == outcome
    lifecycle.note_evidence.assert_not_awaited()
    assert _events(logs, "corroboration_judgment")[0]["outcome"] == outcome


async def test_a_lifecycle_failure_falls_back_to_note_evidence_and_logs():
    lifecycle = _lifecycle()
    lifecycle.promote.side_effect = RuntimeError("db down")
    with capture_logs() as logs:
        result, _, _ = await _run(
            _loop(0.3), FakeSystemOne(_ok(0.93)), lifecycle=lifecycle
        )

    assert isinstance(result, OpenLoop)
    lifecycle.note_evidence.assert_awaited_once()
    assert _events(logs, "corroboration_failed")


async def test_not_same_notes_the_evidence_and_changes_nothing_else():
    existing = _loop(0.3)
    with capture_logs() as logs:
        result, lifecycle, refs = await _run(existing, FakeSystemOne(_ok(0.08)))

    assert isinstance(result, OpenLoop)
    _no_effect_but_note(lifecycle)
    lifecycle.note_evidence.assert_awaited_once_with(
        existing.id, evidence=refs, entity_ids=()
    )
    assert _events(logs, "corroboration_judgment")[0]["outcome"] == "not_same"


async def test_non_independent_makes_no_request():
    existing = _loop(0.3)
    client = FakeSystemOne(_ok(0.99))
    with capture_logs() as logs:
        _, lifecycle, _ = await _run(
            existing, client, store=_store(sources=[_src("email", "T-new")])
        )

    assert client.calls == []
    _no_effect_but_note(lifecycle)
    [skipped] = _events(logs, "corroboration_skipped")
    assert skipped["reason"] == "same_source"


async def test_dropped_source_makes_no_request():
    existing, dropped = _loop(0.3), _loop(0.3, LoopState.DROPPED)
    client = FakeSystemOne(_ok(0.99))
    with capture_logs() as logs:
        _, lifecycle, _ = await _run(
            existing,
            client,
            store=_store(dropped_sources=[_src("email", "T-new")]),
            dropped=dropped,
        )

    assert client.calls == []
    _no_effect_but_note(lifecycle)
    assert _events(logs, "corroboration_skipped")[0]["reason"] == "dropped_source"


async def test_same_evidence_makes_no_request():
    ref = EvidenceRef(kind="episode", id=uuid4())
    client = FakeSystemOne(_ok(0.99))
    _, lifecycle, _ = await _run(
        _loop(0.3), client, store=_store(evidence=[ref]), evidence=[ref]
    )
    assert client.calls == []
    _no_effect_but_note(lifecycle)


async def test_a_match_without_a_key_makes_no_request():
    existing = _loop(0.3)
    client = FakeSystemOne(_ok(0.99))
    store, lifecycle = _store(), _lifecycle()
    corroborator = Corroborator(
        lifecycle=lifecycle,
        loop_store=store,
        system_one_client=client,
        settings=_settings(),
    )
    await corroborator.on_suspected_match(
        existing, None, MatchInput("text", "email", None, (), ())
    )
    assert client.calls == []
    _no_effect_but_note(lifecycle)


# ---- off, unsure and failing paths ----------------------------------------


@pytest.mark.parametrize(
    "block",
    [
        None,
        {"enabled": False, "corroborate_hold": 0.6, "promote_hold": 0.85},
        {"enabled": True, "corroborate_hold": None, "promote_hold": 0.85},
        {"enabled": True, "corroborate_hold": 0.9, "promote_hold": 0.6},
    ],
)
async def test_off_or_uncalibrated_makes_no_request(block):
    client = FakeSystemOne(_ok(0.99))
    settings = {} if block is None else _settings(block)
    _, lifecycle, _ = await _run(_loop(0.3), client, settings=settings)

    assert client.calls == []
    _no_effect_but_note(lifecycle)


async def test_enabled_uncalibrated_warns():
    with capture_logs() as logs:
        await _run(
            _loop(),
            FakeSystemOne(_ok(0.99)),
            settings=_settings(
                {"enabled": True, "corroborate_hold": 0.9, "promote_hold": 0.6}
            ),
        )
    assert any(e["log_level"] == "warning" for e in logs)


async def test_missing_client_notes_the_evidence():
    _, lifecycle, _ = await _run(_loop(), None)
    _no_effect_but_note(lifecycle)


@pytest.mark.parametrize(
    "client",
    [
        FakeSystemOne(SystemOneResult(outcome="skip", skip_reason="timeout")),
        FakeSystemOne(exc=RuntimeError("down")),
        FakeSystemOne(SystemOneResult(outcome="ok", answers={})),
    ],
)
async def test_skip_exception_and_invalid_answer_note_the_evidence(client):
    with capture_logs() as logs:
        _, lifecycle, _ = await _run(_loop(), client)

    _no_effect_but_note(lifecycle)
    [judgment] = _events(logs, "corroboration_judgment")
    assert judgment["outcome"] == "fallback"
    assert judgment["skip_reason"] or judgment["reason"]


async def test_a_failing_note_evidence_is_not_swallowed():
    lifecycle = _lifecycle()
    lifecycle.note_evidence.side_effect = RuntimeError("db down")
    with pytest.raises(RuntimeError):
        await _run(_loop(), None, lifecycle=lifecycle)
