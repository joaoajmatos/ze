"""Tests for CorrelationPushConsumer, CorrelationPushCandidateSource, and
CorrelationJob (Phase 59; split into scan-only + eligibility/send in phase 123
User Story 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4


from ze_agents.claims import ClaimKind
from ze_correlation.job import CorrelationJob
from ze_correlation.push import (
    CorrelationPushCandidateSource,
    CorrelationPushConsumer,
    passes_confidence,
    passes_grounding,
    passes_novelty,
    passes_relevance,
)
from ze_correlation.types import EvidenceRef, Hypothesis

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
    recent_summaries: list[str] | None = None,
    embedder: MagicMock | None = None,
    nli_client: MagicMock | None = None,
) -> tuple[CorrelationPushCandidateSource, dict]:
    if settings is None:
        settings = _make_settings()

    hypothesis_store = MagicMock()
    hypothesis_store.list_unsurfaced = AsyncMock(return_value=unsurfaced or [])
    hypothesis_store.mark_surfaced = AsyncMock()
    hypothesis_store.list_recently_surfaced_summaries = AsyncMock(
        return_value=recent_summaries or []
    )

    notifier = MagicMock()
    notifier.push = AsyncMock()

    if nli_client is None:
        nli_client = AsyncMock()
        nli_client.scores = AsyncMock(return_value=[])
        nli_client.grounding_score = MagicMock(return_value=1.0)

    source = CorrelationPushCandidateSource(
        hypothesis_store=hypothesis_store,
        notifier=notifier,
        settings=settings,
        embedder=embedder,
        nli_client=nli_client,
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


# ── CorrelationPushCandidateSource: eligibility ────────────────────────────────


async def test_eligible_candidates_returns_qualifying_hypotheses():
    h = _make_hypothesis(confidence=0.75, relevance=0.65)
    source, _ = _make_candidate_source(unsurfaced=[h])
    result = await source.eligible_candidates()
    assert result == [h]


async def test_eligible_candidates_excludes_low_confidence():
    h = _make_hypothesis(confidence=0.4, relevance=0.65)
    source, _ = _make_candidate_source(unsurfaced=[h])
    assert await source.eligible_candidates() == []


async def test_eligible_candidates_excludes_low_relevance():
    h = _make_hypothesis(confidence=0.75, relevance=0.2)
    source, _ = _make_candidate_source(unsurfaced=[h])
    assert await source.eligible_candidates() == []


async def test_eligible_candidates_excludes_too_similar_novelty():
    import numpy as np

    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=np.array([1.0, 0.0, 0.0]))
    h = _make_hypothesis(confidence=0.75, relevance=0.65, summary="A connects to B")
    source, _ = _make_candidate_source(
        unsurfaced=[h],
        recent_summaries=["A connects to B almost identically"],
        embedder=embedder,
    )
    assert await source.eligible_candidates() == []


async def test_eligible_candidates_no_embedder_skips_novelty_check():
    h = _make_hypothesis(confidence=0.75, relevance=0.65)
    source, _ = _make_candidate_source(unsurfaced=[h], embedder=None)
    assert await source.eligible_candidates() == [h]


async def test_eligible_candidates_excludes_below_grounding_threshold():
    nli = AsyncMock()
    nli.scores = AsyncMock(
        return_value=[{"contradiction": 0.5, "neutral": 0.4, "entailment": 0.1}]
    )
    nli.grounding_score = MagicMock(return_value=0.1)
    evidence = [
        EvidenceRef(
            kind="signal",
            id=uuid4(),
            label="Stock market moved sharply",
            external_ref=None,
            origin="graph_recall",
            retrieved_at=datetime.now(UTC),
        )
    ]
    h = Hypothesis(
        id=uuid4(),
        summary="User's coffee preference changed",
        narrative="Possible link",
        relation="pattern",
        confidence=0.75,
        relevance=0.65,
        evidence=evidence,
        entities=[uuid4()],
        created_at=datetime.now(UTC),
        claim_kind=ClaimKind.SUSPICION,
    )
    settings = _make_settings()
    settings.config["memory"] = {"nli_grounding_threshold": 0.30}
    source, _ = _make_candidate_source(settings, unsurfaced=[h], nli_client=nli)
    assert await source.eligible_candidates() == []


async def test_eligible_candidates_permissive_on_store_failure():
    source, mocks = _make_candidate_source()
    mocks["hypothesis_store"].list_unsurfaced = AsyncMock(
        side_effect=RuntimeError("db down")
    )
    assert await source.eligible_candidates() == []


# ── CorrelationPushCandidateSource: send ───────────────────────────────────────


async def test_send_pushes_and_marks_surfaced():
    h = _make_hypothesis()
    source, mocks = _make_candidate_source()
    sent = await source.send(h)
    assert sent is True
    mocks["notifier"].push.assert_awaited_once()
    mocks["hypothesis_store"].mark_surfaced.assert_awaited_once_with(h.id)


async def test_send_returns_false_on_notify_failure():
    h = _make_hypothesis()
    source, mocks = _make_candidate_source()
    mocks["notifier"].push = AsyncMock(side_effect=RuntimeError("ntfy down"))
    sent = await source.send(h)
    assert sent is False
    mocks["hypothesis_store"].mark_surfaced.assert_not_awaited()


# ── extracted push-bar primitives (research.md §4) ─────────────────────────────


def test_passes_confidence():
    assert passes_confidence(0.6, 0.5) is True
    assert passes_confidence(0.4, 0.5) is False


def test_passes_relevance():
    assert passes_relevance(0.6, 0.5) is True
    assert passes_relevance(0.4, 0.5) is False


async def test_passes_novelty_no_embedder_is_permissive():
    assert await passes_novelty("summary", ["other"], None, 0.85) is True


async def test_passes_novelty_no_recent_summaries_is_permissive():
    embedder = MagicMock()
    assert await passes_novelty("summary", [], embedder, 0.85) is True


async def test_passes_novelty_rejects_similar_summary():
    import numpy as np

    embedder = MagicMock()
    embedder.encode = MagicMock(return_value=np.array([1.0, 0.0, 0.0]))
    result = await passes_novelty(
        "A connects to B", ["A connects to B almost identically"], embedder, 0.85
    )
    assert result is False


async def test_passes_grounding_no_nli_is_permissive():
    assert await passes_grounding("summary", ["label"], None, 0.3) is True


async def test_passes_grounding_no_evidence_labels_is_permissive():
    nli = AsyncMock()
    assert await passes_grounding("summary", [], nli, 0.3) is True


async def test_passes_grounding_rejects_below_threshold():
    nli = AsyncMock()
    nli.scores = AsyncMock(return_value=[{"entailment": 0.1}])
    nli.grounding_score = MagicMock(return_value=0.1)
    result = await passes_grounding("summary", ["label"], nli, 0.3)
    assert result is False
