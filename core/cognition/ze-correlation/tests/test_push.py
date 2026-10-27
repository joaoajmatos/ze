"""Tests for CorrelationPushConsumer, CorrelationPushCandidateSource, and
CorrelationJob (Phase 59; split into scan-only + eligibility/send in phase 123
User Story 2)."""

from __future__ import annotations

import pytest

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4


from ze_agents.claims import ClaimKind
from ze_correlation.job import CorrelationJob
from ze_correlation.push import (
    CorrelationPushCandidateSource,
    CorrelationPushConsumer,
)
from ze_correlation.types import HypothesisEvidence, Hypothesis
from ze_proactive.candidates import BarThresholds
from ze_proactive.types import OncePer

UTC = timezone.utc


def _make_settings(
    *,
    enabled: bool = True,
    dry_run: bool = False,
    max_seeds_per_run: int = 20,
    seed_lookback_hours: float = 8.0,
    tau_push: float = 0.6,
    tau_relevance: float = 0.5,
    novelty_similarity_max: float = 0.85,
) -> MagicMock:
    s = MagicMock()
    s.config = {
        "correlation": {
            "push": {
                "enabled": enabled,
                "dry_run": dry_run,
                "max_seeds_per_run": max_seeds_per_run,
                "seed_lookback_hours": seed_lookback_hours,
            },
            "salience": {
                "surfacing": {
                    "tau_push": tau_push,
                    "tau_relevance": tau_relevance,
                    "novelty_similarity_max": novelty_similarity_max,
                },
            },
        },
    }
    return s


def _make_hypothesis(
    *,
    confidence: float = 0.75,
    relevance: float = 0.65,
    summary: str = "Signal A connects to Signal B",
) -> Hypothesis:
    return Hypothesis(
        id=uuid4(),
        summary=summary,
        narrative="These two events appear related because...",
        relation="pattern",
        confidence=confidence,
        relevance=relevance,
        evidence=[],
        entities=[uuid4()],
        created_at=datetime.now(UTC),
        claim_kind=ClaimKind.SUSPICION,
        surfaced=False,
    )


def _make_consumer(
    settings: MagicMock | None = None,
    *,
    seed_ids: list[UUID] | None = None,
    hypotheses: list[Hypothesis] | None = None,
) -> tuple[CorrelationPushConsumer, dict]:
    if settings is None:
        settings = _make_settings()

    engine = MagicMock()
    engine.correlate = AsyncMock(return_value=hypotheses or [])

    memory_store = MagicMock()
    memory_store.list_recent_signal_ids = AsyncMock(
        return_value=seed_ids or [uuid4(), uuid4()]
    )

    consumer = CorrelationPushConsumer(
        engine=engine,
        memory_store=memory_store,
        settings=settings,
    )
    mocks = {"engine": engine, "memory_store": memory_store}
    return consumer, mocks


def _make_candidate_source(
    settings: MagicMock | None = None,
    *,
    unsurfaced: list[Hypothesis] | None = None,
) -> tuple[CorrelationPushCandidateSource, dict]:
    if settings is None:
        settings = _make_settings()

    hypothesis_store = MagicMock()
    hypothesis_store.list_unsurfaced = AsyncMock(return_value=unsurfaced or [])
    hypothesis_store.mark_surfaced = AsyncMock()

    notifier = MagicMock()
    notifier.notify = AsyncMock(return_value="delivered")

    source = CorrelationPushCandidateSource(
        hypothesis_store=hypothesis_store,
        notifier=notifier,
        settings=settings,
    )
    mocks = {"hypothesis_store": hypothesis_store, "notifier": notifier}
    return source, mocks


# ── seed selection ────────────────────────────────────────────────────────────


async def test_seed_selection_respects_max_seeds_per_run():
    settings = _make_settings(max_seeds_per_run=5)
    consumer, mocks = _make_consumer(settings)
    await consumer.run_once()
    limit_arg = mocks["memory_store"].list_recent_signal_ids.call_args[0][1]
    assert limit_arg == 5


async def test_seed_selection_uses_lookback_window():
    settings = _make_settings(seed_lookback_hours=4.0)
    consumer, mocks = _make_consumer(settings)
    await consumer.run_once()
    since_arg = mocks["memory_store"].list_recent_signal_ids.call_args[0][0]
    # since should be approximately 4 hours ago
    delta = datetime.now(UTC) - since_arg
    assert abs(delta.total_seconds() - 4 * 3600) < 5


async def test_explicit_seeds_skip_memory_query():
    consumer, mocks = _make_consumer()
    seeds = [uuid4(), uuid4()]
    await consumer.run_once(seeds=seeds)
    mocks["memory_store"].list_recent_signal_ids.assert_not_called()
    mocks["engine"].correlate.assert_awaited_once_with(seeds, mode="proactive")


async def test_no_seeds_returns_early():
    consumer, mocks = _make_consumer(seed_ids=[])
    mocks["memory_store"].list_recent_signal_ids = AsyncMock(return_value=[])
    result = await consumer.run_once()
    assert result == []
    mocks["engine"].correlate.assert_not_awaited()


async def test_returns_all_formed_hypotheses():
    h1 = _make_hypothesis()
    h2 = _make_hypothesis()
    consumer, _ = _make_consumer(hypotheses=[h1, h2])
    result = await consumer.run_once()
    assert result == [h1, h2]


async def test_disabled_with_no_dry_run_returns_early():
    settings = _make_settings(enabled=False, dry_run=False)
    consumer, mocks = _make_consumer(settings)
    result = await consumer.run_once()
    assert result == []
    mocks["engine"].correlate.assert_not_awaited()


# ── CorrelationJob ────────────────────────────────────────────────────────────


async def test_correlation_job_delegates_to_consumer():
    consumer = MagicMock()
    consumer.run_once = AsyncMock(return_value=[])
    job = CorrelationJob(push_consumer=consumer)
    assert job.job_id == "correlation_scan"
    await job.run()
    consumer.run_once.assert_awaited_once()


# ── CorrelationPushCandidateSource: candidates ────────────────────────────────


async def test_candidates_describe_each_unsurfaced_hypothesis():
    evidence = [
        HypothesisEvidence(
            kind="signal",
            id=uuid4(),
            label="Stock market moved sharply",
            external_ref=None,
            origin="graph_recall",
            retrieved_at=datetime.now(UTC),
        ),
        HypothesisEvidence(
            kind="signal",
            id=uuid4(),
            label="",
            external_ref=None,
            origin="graph_recall",
            retrieved_at=datetime.now(UTC),
        ),
    ]
    h = _make_hypothesis(confidence=0.75, relevance=0.65)
    h = Hypothesis(**{**h.__dict__, "evidence": evidence})
    source, _ = _make_candidate_source(unsurfaced=[h])

    (candidate,) = await source.candidates()

    assert candidate.source_kind == "hypothesis"
    assert candidate.source_id == h.id
    assert candidate.entity is h
    assert candidate.body == f"{h.summary}\n\n{h.narrative}"
    assert candidate.claim == h.summary
    assert candidate.confidence == 0.75
    assert await candidate.relevance() == 0.65
    assert await candidate.evidence_labels() == ("Stock market moved sharply",)
    assert candidate.once_per == OncePer(f"hypothesis:{h.id}")


async def test_candidates_apply_no_bar_condition():
    h = _make_hypothesis(confidence=0.1, relevance=0.0)
    source, _ = _make_candidate_source(unsurfaced=[h])
    assert len(await source.candidates()) == 1


def test_thresholds_come_from_config_and_nli():
    settings = _make_settings(
        tau_push=0.7, tau_relevance=0.4, novelty_similarity_max=0.8
    )
    settings.config["memory"] = {"nli_grounding_threshold": 0.25}
    source, _ = _make_candidate_source(settings)
    assert source.thresholds == BarThresholds(
        confidence=0.7,
        relevance=0.4,
        novelty_similarity_max=0.8,
        grounding=0.25,
        inline_cooldown_hours=None,
    )


async def test_candidates_store_failure_returns_empty():
    source, mocks = _make_candidate_source()
    mocks["hypothesis_store"].list_unsurfaced = AsyncMock(
        side_effect=RuntimeError("db down")
    )
    assert await source.candidates() == []


# ── correlation push switch (phase 170 US5) ───────────────────────────────────


async def test_candidates_disabled_skips_store():
    settings = _make_settings(enabled=False, dry_run=False)
    h = _make_hypothesis(confidence=0.75, relevance=0.65)
    source, mocks = _make_candidate_source(settings, unsurfaced=[h])

    assert await source.candidates() == []
    mocks["hypothesis_store"].list_unsurfaced.assert_not_awaited()


@pytest.mark.parametrize("dry_run", [True, False])
async def test_dry_run_follows_config(dry_run):
    source, _ = _make_candidate_source(_make_settings(dry_run=dry_run))
    assert source.dry_run is dry_run


async def test_candidates_read_through_list_unsurfaced():
    """list_unsurfaced carries the dismissed-feedback predicate (pinned in test_store)."""
    source, mocks = _make_candidate_source()
    await source.candidates()
    mocks["hypothesis_store"].list_unsurfaced.assert_awaited()


# ── CorrelationPushCandidateSource: send ───────────────────────────────────────


async def _send(source, h):
    (candidate,) = await source.candidates()
    return await source.send(candidate)


async def test_send_pushes_with_candidate_claim_and_marks_surfaced():
    h = _make_hypothesis()
    source, mocks = _make_candidate_source(unsurfaced=[h])
    assert await _send(source, h) == "delivered"
    mocks["notifier"].notify.assert_awaited_once()
    kw = mocks["notifier"].notify.await_args.kwargs
    assert kw["once_per"] == OncePer(f"hypothesis:{h.id}")
    assert "budget_key" not in kw
    assert kw["target_type"] == "hypothesis"
    assert kw["target_id"] == str(h.id)
    mocks["hypothesis_store"].mark_surfaced.assert_awaited_once_with(h.id)


async def test_send_marks_surfaced_when_held():
    h = _make_hypothesis()
    source, mocks = _make_candidate_source(unsurfaced=[h])
    mocks["notifier"].notify = AsyncMock(return_value="held")
    assert await _send(source, h) == "held"
    mocks["hypothesis_store"].mark_surfaced.assert_awaited_once_with(h.id)


@pytest.mark.parametrize("outcome", ["failed", "deduped", "suppressed_budget"])
async def test_send_does_not_mark_surfaced_when_not_sent(outcome):
    h = _make_hypothesis()
    source, mocks = _make_candidate_source(unsurfaced=[h])
    mocks["notifier"].notify = AsyncMock(return_value=outcome)
    assert await _send(source, h) == outcome
    mocks["hypothesis_store"].mark_surfaced.assert_not_awaited()
