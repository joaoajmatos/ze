from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

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


# ── passes_push_bar (T032, T038) ───────────────────────────────────────────────


def _relevance_model(value: float = 0.8) -> MagicMock:
    model = MagicMock()
    model.build = AsyncMock(return_value=object())
    model.score = MagicMock(return_value=SimpleNamespace(value=value, contributions=[]))
    return model


def _push_bar_surfacer(
    *,
    relevance_value: float = 0.8,
    recent_payloads: list[str] | None = None,
    inline_sent: bool = False,
    budget_count: int = 0,
) -> LoopSurfacer:
    push_log = AsyncMock()
    push_log.list_recent_payloads = AsyncMock(return_value=recent_payloads or [])
    push_log.was_sent_within_hours = AsyncMock(return_value=inline_sent)
    push_log.window_sent_at = AsyncMock(
        return_value=[
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i)
            for i in range(budget_count)
        ]
    )
    push_log.log = AsyncMock()

    return LoopSurfacer(
        loop_store=AsyncMock(),
        graph_store=AsyncMock(),
        push_log=push_log,
        pool=None,
        relevance_model=_relevance_model(relevance_value),
        embedder=None,
    )


async def test_passes_push_bar_clears_all_gates():
    loop = _loop(confidence=0.8)
    surfacer = _push_bar_surfacer(relevance_value=0.8)
    assert await surfacer.passes_push_bar(loop, loop.drift_rationale) is True


async def test_passes_push_bar_rejects_low_confidence():
    loop = _loop(confidence=0.1)
    surfacer = _push_bar_surfacer()
    assert await surfacer.passes_push_bar(loop, loop.drift_rationale) is False


async def test_passes_push_bar_rejects_low_relevance():
    loop = _loop(confidence=0.8)
    surfacer = _push_bar_surfacer(relevance_value=0.1)
    assert await surfacer.passes_push_bar(loop, loop.drift_rationale) is False


# ── eligible_candidates / send (phase 123 User Story 2) ────────────────────────


def _eligibility_surfacer(
    *, loops: list[OpenLoop], relevance_value: float = 0.8
) -> LoopSurfacer:
    push_log = AsyncMock()
    push_log.list_recent_payloads = AsyncMock(return_value=[])
    push_log.was_sent_within_hours = AsyncMock(return_value=False)

    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=loops)

    return LoopSurfacer(
        loop_store=loop_store,
        graph_store=AsyncMock(),
        push_log=push_log,
        pool=None,
        relevance_model=_relevance_model(relevance_value),
        embedder=None,
    )


async def test_eligible_candidates_returns_loops_passing_the_bar():
    loop = _loop(confidence=0.8)
    surfacer = _eligibility_surfacer(loops=[loop])
    candidates = await surfacer.eligible_candidates()
    assert candidates == [loop]


async def test_eligible_candidates_excludes_low_confidence_loops():
    loop = _loop(confidence=0.1)
    surfacer = _eligibility_surfacer(loops=[loop])
    assert await surfacer.eligible_candidates() == []


async def test_eligible_candidates_skips_loops_without_rationale():
    loop = _loop(confidence=0.8, drift_rationale=None)
    surfacer = _eligibility_surfacer(loops=[loop])
    assert await surfacer.eligible_candidates() == []


async def test_send_pushes_when_loop_still_drifting():
    loop = _loop(confidence=0.8)
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=loop)
    notifier = AsyncMock()
    notifier.notify = AsyncMock(return_value="delivered")
    surfacer = LoopSurfacer(
        loop_store=loop_store,
        graph_store=AsyncMock(),
        push_log=AsyncMock(),
        notifier=notifier,
    )

    outcome = await surfacer.send(loop)

    assert outcome == "delivered"
    notifier.notify.assert_awaited_once()
    args = notifier.notify.await_args
    assert args.args[0].event_type == "loop_drift"
    assert args.kwargs["budget_key"] == f"loop:{loop.id}"
    assert args.kwargs["target_type"] == "open_loop"


async def test_send_returns_false_when_loop_no_longer_drifting():
    loop = _loop(confidence=0.8)
    resolved = _loop(id=loop.id, state=LoopState.CLOSED)
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=resolved)
    notifier = AsyncMock()
    surfacer = LoopSurfacer(
        loop_store=loop_store,
        graph_store=AsyncMock(),
        push_log=AsyncMock(),
        notifier=notifier,
    )

    outcome = await surfacer.send(loop)

    assert outcome is None
    notifier.notify.assert_not_awaited()


async def test_passes_push_bar_rejects_within_inline_cooldown():
    loop = _loop(confidence=0.8)
    surfacer = _push_bar_surfacer(relevance_value=0.8, inline_sent=True)
    assert await surfacer.passes_push_bar(loop, loop.drift_rationale) is False


# ── grounding checks the title (phase 170) ─────────────────────────────────────


class _RecordingNli:
    def __init__(self, score: float = 0.9):
        self.pairs: list = []
        self._score = score

    async def scores(self, pairs):
        self.pairs.extend(pairs)
        return [self._score] * len(pairs)

    def grounding_score(self, summary, labels, scores=None):
        return max(scores) if scores else 0.0


async def test_grounding_hypothesis_is_the_loop_title_not_the_rationale(monkeypatch):
    from ze_worldstate import surfacing

    async def fake_summaries(pool, loop_store, loop_id):
        return [
            {
                "type": "episode",
                "id": uuid4(),
                "summary": "I need to send Maria the contract",
            }
        ]

    monkeypatch.setattr(surfacing, "_fetch_evidence_summaries", fake_summaries)
    loop = _loop(confidence=0.8)
    nli = _RecordingNli()

    passed = await _push_bar_surfacer().passes_push_bar(
        loop, loop.drift_rationale, nli_client=nli
    )

    assert passed is True
    assert nli.pairs == [("I need to send Maria the contract", loop.title)]


async def test_grounding_fails_when_the_title_is_not_supported(monkeypatch):
    from ze_worldstate import surfacing

    async def fake_summaries(pool, loop_store, loop_id):
        return [{"type": "episode", "id": uuid4(), "summary": "unrelated"}]

    monkeypatch.setattr(surfacing, "_fetch_evidence_summaries", fake_summaries)
    loop = _loop(confidence=0.8)
    assert (
        await _push_bar_surfacer().passes_push_bar(
            loop, loop.drift_rationale, nli_client=_RecordingNli(score=0.01)
        )
        is False
    )


async def test_grounding_passes_without_evidence_labels():
    loop = _loop(confidence=0.8)
    nli = _RecordingNli(score=0.0)
    assert (
        await _push_bar_surfacer().passes_push_bar(
            loop, loop.drift_rationale, nli_client=nli
        )
        is True
    )
    assert nli.pairs == []
