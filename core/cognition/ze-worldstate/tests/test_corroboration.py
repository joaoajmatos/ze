from __future__ import annotations

from uuid import uuid4

import pytest
from ze_plugin.contribution import EvidenceRef

from ze_worldstate.corroboration import (
    CORROBORATED_CAP,
    CORROBORATION_WEIGHT,
    PROMOTED_CONFIDENCE,
    PROMOTED_WINDOW_DAYS,
    corroborated_confidence,
    is_independent,
)
from ze_worldstate.drift import DEFAULT_DRIFT_WINDOW_DAYS
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
    assert is_independent(key, [other, ref], [_src("conversation", "c1")], [ref], []) == (
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
    assert PROMOTED_WINDOW_DAYS == DEFAULT_DRIFT_WINDOW_DAYS == 7


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

from ze_worldstate.corroboration import corroborate_match  # noqa: E402
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


def _store(sources=None, evidence=None, dropped_sources=None, added=True):
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
    row = LoopSource(
        id=uuid4(), loop_id=uuid4(), role=LoopSourceRole.CORROBORATION, key=KEY
    )
    store.add_source = AsyncMock(return_value=row if added else None)
    store.promote = AsyncMock(return_value=_loop(0.7, LoopState.ACTIVE))
    store.set_confidence = AsyncMock()
    store.mark_source_promoted = AsyncMock()
    return store, row


async def _run(existing, store, client, *, settings=None, dropped=None, evidence=None):
    link = AsyncMock()
    store.owner["id"] = existing.id
    await corroborate_match(
        existing=existing,
        text="Reminder: the budget reply to Ana is still pending.",
        inflow="email",
        key=KEY,
        evidence_refs=evidence or [EvidenceRef(kind="episode", id=uuid4())],
        entity_ids=[],
        dropped=dropped,
        loop_store=store,
        system_one_client=client,
        settings=_settings() if settings is None else settings,
        link=link,
    )
    return link


def _events(logs, name):
    return [e for e in logs if e["event"] == name]


async def test_corroborate_band_raises_confidence_and_writes_a_source_row():
    existing = _loop(0.3)
    store, _ = _store()
    client = FakeSystemOne(_ok(0.8))
    with capture_logs() as logs:
        link = await _run(existing, store, client)

    link.assert_awaited_once()
    store.set_confidence.assert_awaited_once()
    assert store.set_confidence.await_args.args[0] == existing.id
    assert store.set_confidence.await_args.args[1] == pytest.approx(0.58)
    source = store.add_source.await_args.args[0]
    assert source.role is LoopSourceRole.CORROBORATION
    assert source.promoted is False
    assert (source.same_concern, source.model, source.latency_ms) == (
        0.8,
        "test-model",
        42,
    )
    assert source.key == KEY
    store.promote.assert_not_awaited()
    assert len(client.calls) == 1 and client.calls[0][2] == 1
    [judgment] = _events(logs, "corroboration_judgment")
    assert judgment["outcome"] == "corroborate"
    assert judgment["loop_id"] == str(existing.id)
    for field in ("inflow", "reason", "score", "latency_ms", "skip_reason"):
        assert field in judgment


async def test_second_corroboration_is_capped():
    existing = _loop(0.58)
    store, _ = _store()
    await _run(existing, store, FakeSystemOne(_ok(0.8)))
    assert store.set_confidence.await_args.args[1] == pytest.approx(0.6)


async def test_promote_calls_the_guarded_update_then_marks_the_source():
    existing = _loop(0.3)
    store, row = _store()
    with capture_logs() as logs:
        await _run(existing, store, FakeSystemOne(_ok(0.93)))

    store.promote.assert_awaited_once_with(existing.id, confidence=0.7, window_days=7)
    store.mark_source_promoted.assert_awaited_once_with(row.id)
    assert _events(logs, "corroboration_judgment")[0]["outcome"] == "promote"


async def test_promote_lost_race_leaves_promoted_false():
    existing = _loop(0.3)
    store, _ = _store()
    store.promote = AsyncMock(return_value=None)
    with capture_logs() as logs:
        await _run(existing, store, FakeSystemOne(_ok(0.93)))

    store.mark_source_promoted.assert_not_awaited()
    assert _events(logs, "corroboration_judgment")[0]["outcome"] == "corroborate"


async def test_duplicate_source_stops_before_confidence_or_promote():
    existing = _loop(0.3)
    store, _ = _store(added=False)
    with capture_logs() as logs:
        await _run(existing, store, FakeSystemOne(_ok(0.93)))

    store.set_confidence.assert_not_awaited()
    store.promote.assert_not_awaited()
    assert _events(logs, "corroboration_judgment")[0]["reason"] == "duplicate_source"


async def test_exception_gives_the_170_behavior_and_logs_failure():
    existing = _loop(0.3)
    store, _ = _store()
    store.add_source = AsyncMock(side_effect=RuntimeError("db down"))
    with capture_logs() as logs:
        link = await _run(existing, store, FakeSystemOne(_ok(0.93)))

    assert link.await_count >= 1
    store.promote.assert_not_awaited()
    assert _events(logs, "corroboration_failed")


async def test_not_same_links_and_changes_nothing_else():
    existing = _loop(0.3)
    store, _ = _store()
    with capture_logs() as logs:
        link = await _run(existing, store, FakeSystemOne(_ok(0.08)))

    link.assert_awaited_once()
    store.add_source.assert_not_awaited()
    store.set_confidence.assert_not_awaited()
    assert _events(logs, "corroboration_judgment")[0]["outcome"] == "not_same"


async def test_non_independent_makes_no_request():
    existing = _loop(0.3)
    store, _ = _store(sources=[_src("email", "T-new")])
    client = FakeSystemOne(_ok(0.99))
    with capture_logs() as logs:
        link = await _run(existing, store, client)

    assert client.calls == []
    link.assert_awaited_once()
    store.add_source.assert_not_awaited()
    [skipped] = _events(logs, "corroboration_skipped")
    assert skipped["reason"] == "same_source"


async def test_dropped_source_makes_no_request():
    existing, dropped = _loop(0.3), _loop(0.3, LoopState.DROPPED)
    store, _ = _store(dropped_sources=[_src("email", "T-new")])
    client = FakeSystemOne(_ok(0.99))
    with capture_logs() as logs:
        await _run(existing, store, client, dropped=dropped)

    assert client.calls == []
    assert _events(logs, "corroboration_skipped")[0]["reason"] == "dropped_source"


async def test_same_evidence_makes_no_request():
    existing = _loop(0.3)
    ref = EvidenceRef(kind="episode", id=uuid4())
    store, _ = _store(evidence=[ref])
    client = FakeSystemOne(_ok(0.99))
    await _run(existing, store, client, evidence=[ref])
    assert client.calls == []


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
    existing = _loop(0.3)
    store, _ = _store()
    client = FakeSystemOne(_ok(0.99))
    settings = {} if block is None else _settings(block)
    link = await _run(existing, store, client, settings=settings)

    assert client.calls == []
    link.assert_awaited_once()
    store.add_source.assert_not_awaited()
    store.set_confidence.assert_not_awaited()
    store.promote.assert_not_awaited()


async def test_enabled_uncalibrated_warns():
    with capture_logs() as logs:
        await _run(
            _loop(),
            _store()[0],
            FakeSystemOne(_ok(0.99)),
            settings=_settings({"enabled": True, "corroborate_hold": 0.9, "promote_hold": 0.6}),
        )
    assert any(e["log_level"] == "warning" for e in logs)


async def test_missing_client_is_the_170_behavior():
    existing = _loop()
    store, _ = _store()
    link = await _run(existing, store, None)
    link.assert_awaited_once()
    store.add_source.assert_not_awaited()


@pytest.mark.parametrize(
    "client",
    [
        FakeSystemOne(SystemOneResult(outcome="skip", skip_reason="timeout")),
        FakeSystemOne(exc=RuntimeError("down")),
        FakeSystemOne(SystemOneResult(outcome="ok", answers={})),
    ],
)
async def test_skip_exception_and_invalid_answer_are_the_170_behavior(client):
    existing = _loop()
    store, _ = _store()
    with capture_logs() as logs:
        link = await _run(existing, store, client)

    link.assert_awaited_once()
    store.add_source.assert_not_awaited()
    store.set_confidence.assert_not_awaited()
    [judgment] = _events(logs, "corroboration_judgment")
    assert judgment["outcome"] == "fallback"
    assert judgment["skip_reason"] or judgment["reason"]
