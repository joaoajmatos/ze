from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_proactive.types import OncePer

from ze_worldstate.bootstrap import LoopPushSettings
from ze_worldstate.surfacing import LoopSurfacer, format_hedged_mention
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop


def _loop(**overrides) -> OpenLoop:
    base = dict(
        id=uuid4(),
        title="Send Maria the contract",
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.5,
        state=LoopState.DRIFTING,
        drift_rationale="No corroborating evidence since confirmation on 2026-07-10.",
    )
    base.update(overrides)
    return OpenLoop(**base)


def test_format_hedged_mention_starts_with_hedge_prefix():
    text = format_hedged_mention("Renew passport", "Deadline elapsed.")
    assert text.startswith("It looks like")
    assert "Renew passport" in text
    assert "Deadline elapsed." in text


def test_format_hedged_mention_without_rationale():
    text = format_hedged_mention("Renew passport", None)
    assert text.startswith("It looks like")
    assert text.endswith(".")


def _relevance_model(value: float = 0.8) -> MagicMock:
    model = MagicMock()
    model.build = AsyncMock(return_value=object())
    model.score = MagicMock(return_value=SimpleNamespace(value=value, contributions=[]))
    return model


def _surfacer(
    loops: list[OpenLoop] | None = None,
    *,
    settings: LoopPushSettings | None = None,
    notifier=None,
    relevance_model=None,
) -> LoopSurfacer:
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=loops or [])
    return LoopSurfacer(
        loop_store=loop_store,
        graph_store=AsyncMock(),
        pool=None,
        relevance_model=relevance_model or _relevance_model(),
        notifier=notifier or AsyncMock(),
        settings=settings or LoopPushSettings(),
    )


async def test_candidates_carry_the_fields_the_bar_reads():
    loop = _loop(confidence=0.8)
    surfacer = _surfacer([loop])

    (candidate,) = await surfacer.candidates()

    assert candidate.source_kind == "loop"
    assert candidate.source_id == loop.id
    assert candidate.entity is loop
    assert candidate.body == format_hedged_mention(loop.title, loop.drift_rationale)
    assert candidate.claim == loop.title
    assert candidate.confidence == 0.8
    assert candidate.once_per == OncePer(f"loop:{loop.id}", within=timedelta(days=7))


async def test_candidates_skip_loops_without_rationale():
    surfacer = _surfacer([_loop(drift_rationale=None), _loop()])
    assert len(await surfacer.candidates()) == 1


async def test_candidates_queries_only_drifting_loops():
    surfacer = _surfacer([])
    await surfacer.candidates()
    surfacer._loop_store.list.assert_awaited_once_with([LoopState.DRIFTING.value])


async def test_once_per_window_follows_repush_after_days():
    surfacer = _surfacer([_loop()], settings=LoopPushSettings(repush_after_days=2.0))
    (candidate,) = await surfacer.candidates()
    assert candidate.once_per.within == timedelta(days=2)


async def test_relevance_is_read_only_when_the_thunk_is_awaited():
    model = _relevance_model(0.7)
    surfacer = _surfacer([_loop()], relevance_model=model)
    (candidate,) = await surfacer.candidates()

    model.build.assert_not_awaited()
    assert await candidate.relevance() == 0.7
    model.build.assert_awaited_once()


async def test_evidence_labels_are_read_lazily_and_drop_empty_summaries(monkeypatch):
    fetch = AsyncMock(return_value=[{"summary": "Maria asked"}, {"summary": ""}, {}])
    monkeypatch.setattr("ze_worldstate.surfacing._fetch_evidence_summaries", fetch)
    surfacer = _surfacer([_loop()])
    (candidate,) = await surfacer.candidates()

    fetch.assert_not_awaited()
    assert await candidate.evidence_labels() == ("Maria asked",)


async def test_thresholds_come_from_the_settings():
    surfacer = _surfacer(
        settings=LoopPushSettings(
            thresholds={"tau_confidence": 0.7}, inline_cooldown_hours=6.0
        )
    )
    thresholds = surfacer.thresholds
    assert thresholds.confidence == 0.7
    assert thresholds.inline_cooldown_hours == 6.0


def test_surfacer_is_a_live_loop_source():
    surfacer = _surfacer()
    assert surfacer.source_kind == "loop"
    assert surfacer.dry_run is False


async def test_send_pushes_when_loop_still_drifting():
    loop = _loop()
    notifier = AsyncMock()
    notifier.notify = AsyncMock(return_value="delivered")
    surfacer = _surfacer([loop], notifier=notifier)
    surfacer._loop_store.get = AsyncMock(return_value=loop)
    (candidate,) = await surfacer.candidates()

    outcome = await surfacer.send(candidate)

    assert outcome == "delivered"
    args, kwargs = notifier.notify.call_args
    assert args[1:] == ("Open loop", candidate.body)
    assert kwargs["target_type"] == "open_loop"
    assert kwargs["target_id"] == str(loop.id)
    assert kwargs["once_per"] == candidate.once_per


async def test_send_returns_none_when_loop_no_longer_drifting():
    loop = _loop()
    notifier = AsyncMock()
    surfacer = _surfacer([loop], notifier=notifier)
    (candidate,) = await surfacer.candidates()

    for current in (_loop(id=loop.id, state=LoopState.CLOSED), None):
        surfacer._loop_store.get = AsyncMock(return_value=current)
        assert await surfacer.send(candidate) is None

    notifier.notify.assert_not_called()
