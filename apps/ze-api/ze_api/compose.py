from __future__ import annotations

from typing import Any

from ze_agents.settings import Settings as CoreSettings
from ze_automation.bootstrap import register_proactive_jobs as register_automation_jobs
from ze_core.bootstrap import register_engine_jobs
from ze_correlation.bootstrap import (
    register_proactive_jobs as register_correlation_jobs,
)
from ze_memory.bootstrap import (
    consolidation_enabled,
    register_dream_jobs,
    register_memory_jobs,
)
from ze_priority.arbitration import AttentionArbitrationJob
from ze_proactive.bootstrap import register_notification_jobs, shared_push_budget
from ze_proactive.notification_store import NotificationStore
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.push_log_store import PushLogStore
from ze_proactive.scheduler import ProactiveScheduler
from ze_skills.bootstrap import register_proactive_jobs as register_skills_jobs
from ze_worldstate.bootstrap import register_proactive_jobs as register_worldstate_jobs
from ze_logging import get_logger

log = get_logger(__name__)


def register_all_proactive_jobs(
    scheduler: ProactiveScheduler,
    *,
    settings: Any,
    core_settings: CoreSettings,
    automation: Any,
    correlation: Any,
    worldstate: Any = None,
    loop_surfacer: Any = None,
    priority_view: Any = None,
    correlation_push_source: Any = None,
    skills_stack: Any = None,
    shared: Any,
    plugins: list,
    notifier: ProactiveNotifier,
    push_log_store: PushLogStore,
    notification_store: NotificationStore | None = None,
    dream_job: Any = None,
    pool: Any = None,
) -> None:
    register_automation_jobs(
        scheduler,
        settings,
        automation,
        notifier=notifier,
        push_log_store=push_log_store,
    )
    if notification_store is not None:
        register_notification_jobs(scheduler, settings, notification_store)
    register_engine_jobs(automation.workflow_scheduler, settings, shared)
    register_memory_jobs(scheduler, settings, shared)
    register_correlation_jobs(
        scheduler,
        settings,
        correlation,
        shared=shared,
    )
    if worldstate is not None:
        register_worldstate_jobs(scheduler, settings, worldstate)
    if (
        loop_surfacer is not None
        and priority_view is not None
        and correlation_push_source is not None
    ):
        arbitration_cfg = (
            (getattr(settings, "config", None) or {})
            .get("proactive", {})
            .get("attention_arbitration", {})
        )
        if arbitration_cfg.get("enabled", True):
            arbitration_job = AttentionArbitrationJob(
                priority_view=priority_view,
                loop_surfacer=loop_surfacer,
                correlation_push_source=correlation_push_source,
                push_log=push_log_store,
                max_pushes_per_day=shared_push_budget(settings),
            )
            scheduler.add_cron_job(
                fn=arbitration_job.run,
                cron=arbitration_cfg.get("cron", "0 */4 * * *"),
                job_id=AttentionArbitrationJob.job_id,
            )
            log.info(
                "attention_arbitration_job_scheduled",
                cron=arbitration_cfg.get("cron", "0 */4 * * *"),
            )
    if skills_stack is not None:
        register_skills_jobs(scheduler, settings, skills_stack)
    for plugin in plugins:
        plugin.register_proactive_jobs(
            scheduler,
            core_settings,
            consolidation_enabled=consolidation_enabled(settings),
        )
    if dream_job is not None:
        register_dream_jobs(scheduler, settings, dream_job, pool=pool)


async def reconcile_in_progress_workspace_runs(store: Any, run_watcher: Any) -> None:
    """Startup reconciliation (Phase 116 D5) — re-adopt any `workspace_runs` row
    still `ended_at IS NULL` from before a restart, so a detached run's
    follow-through (follow-up turn + completion push) is not silently stranded.
    Mirrors Phase 13's reminder startup replay: same problem, an in-memory
    background watcher that must survive a process restart.
    """
    runs = await store.list_in_progress()
    for run in runs:
        try:
            await run_watcher.reattach(run)
        except Exception as exc:
            log.warning(
                "workspace_run_reattach_failed", run_id=str(run.id), error=str(exc)
            )
