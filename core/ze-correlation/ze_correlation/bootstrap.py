from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ze_logging import get_logger
from ze_correlation import (
    CorrelationEngine,
    CorrelationJob,
    CorrelationPushConsumer,
    PostgresHypothesisStore,
)
from ze_correlation.jobs.hypothesis_decay import HypothesisDecayJob
from ze_correlation.push import CorrelationPushCandidateSource
from ze_memory.relevance import RelevanceModel
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.scheduler import ProactiveScheduler

log = get_logger(__name__)


@dataclass
class CorrelationStack:
    hypothesis_store: PostgresHypothesisStore
    correlation_engine: CorrelationEngine
    relevance_model: RelevanceModel


def build_correlation_stack(shared: Any, settings: Any) -> CorrelationStack:
    hypothesis_store = PostgresHypothesisStore(pool=shared.pool)
    relevance_model = RelevanceModel(memory_store=shared.memory_store)
    correlation_engine = CorrelationEngine(
        memory_store=shared.memory_store,
        relevance_model=relevance_model,
        llm_client=shared.openrouter_client,
        hypothesis_store=hypothesis_store,
        settings=settings,
    )
    return CorrelationStack(
        hypothesis_store=hypothesis_store,
        correlation_engine=correlation_engine,
        relevance_model=relevance_model,
    )


def build_correlation_push_candidate_source(
    stack: CorrelationStack,
    notifier: ProactiveNotifier,
    settings: Any,
    embedder: Any = None,
    nli_client: Any = None,
) -> CorrelationPushCandidateSource:
    """Constructed in `ze_api/container.py` for `AttentionArbitrationJob`
    (phase 123 User Story 2) — the push-eligibility/send half of what
    `CorrelationPushConsumer` used to do end-to-end."""
    return CorrelationPushCandidateSource(
        hypothesis_store=stack.hypothesis_store,
        notifier=notifier,
        settings=settings,
        embedder=embedder,
        nli_client=nli_client,
    )


def register_proactive_jobs(
    scheduler: ProactiveScheduler,
    settings: Any,
    stack: CorrelationStack,
    *,
    shared: Any,
) -> None:
    raw_cfg = getattr(settings, "config", {}) or {}
    _push_cfg = raw_cfg.get("correlation", {}).get("push", {})
    _push_schedule = _push_cfg.get("schedule", "0 */4 * * *")
    push_consumer = CorrelationPushConsumer(
        engine=stack.correlation_engine,
        memory_store=shared.memory_store,
        settings=settings,
    )
    correlation_job = CorrelationJob(push_consumer=push_consumer)
    scheduler.add_cron_job(
        fn=correlation_job.run,
        cron=_push_schedule,
        job_id=CorrelationJob.job_id,
    )
    log.info("correlation_push_job_scheduled", cron=_push_schedule)

    _decay_cfg = raw_cfg.get("correlation", {}).get("hypothesis_decay", {})
    _decay_schedule = _decay_cfg.get("schedule", "0 3 * * *")
    decay_job = HypothesisDecayJob(hypothesis_store=stack.hypothesis_store)
    scheduler.add_cron_job(
        fn=decay_job.run,
        cron=_decay_schedule,
        job_id=HypothesisDecayJob.job_id,
    )
    log.info("hypothesis_decay_job_scheduled", cron=_decay_schedule)
