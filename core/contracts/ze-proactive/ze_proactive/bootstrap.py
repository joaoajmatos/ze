from __future__ import annotations

from typing import Any

from ze_logging import get_logger
from ze_proactive.jobs.prune_notifications import PruneNotificationsJob
from ze_proactive.notification_store import NotificationStore
from ze_proactive.scheduler import ProactiveScheduler

log = get_logger(__name__)

_DEFAULT_MAX_PUSHES_PER_DAY = 3


def shared_push_budget(settings: Any) -> int:
    """`proactive.budget.max_pushes_per_day` — the one shared attention budget
    every push mechanism now claims against (FR-005), for constructor injection
    into `ze-correlation`/`ze-worldstate`/`ze-priority` consumers."""
    cfg = (getattr(settings, "config", None) or {}).get("proactive", {})
    return int(cfg.get("budget", {}).get("max_pushes_per_day", _DEFAULT_MAX_PUSHES_PER_DAY))


def register_notification_jobs(
    scheduler: ProactiveScheduler,
    settings: Any,
    notification_store: NotificationStore,
) -> None:
    cfg = (
        (getattr(settings, "config", None) or {})
        .get("proactive", {})
        .get("notifications", {})
    )
    cron = cfg.get("prune_cron", "0 4 * * *")
    retention_days = int(cfg.get("retention_days", 90))

    job = PruneNotificationsJob(
        notification_store=notification_store, retention_days=retention_days
    )
    scheduler.add_cron_job(fn=job.run, cron=cron, job_id=job.job_id)
    log.info(
        "notifications_prune_job_scheduled", cron=cron, retention_days=retention_days
    )
