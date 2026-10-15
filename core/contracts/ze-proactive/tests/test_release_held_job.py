from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ze_proactive.jobs.release_held import QuietHoursReleaseJob


async def test_run_delegates_to_deliver_held():
    notifier = AsyncMock()
    notifier.deliver_held = AsyncMock(return_value=2)
    await QuietHoursReleaseJob(notifier).run()
    notifier.deliver_held.assert_awaited_once()


async def test_run_with_nothing_held_is_quiet():
    notifier = AsyncMock()
    notifier.deliver_held = AsyncMock(return_value=0)
    await QuietHoursReleaseJob(notifier).run()
    notifier.deliver_held.assert_awaited_once()


async def test_store_error_is_logged_not_raised():
    notifier = AsyncMock()
    notifier.deliver_held = AsyncMock(side_effect=RuntimeError("db down"))
    await QuietHoursReleaseJob(notifier).run()


def test_job_id():
    assert QuietHoursReleaseJob.job_id == "quiet_hours_release"


def test_registered_without_catch_up_on_release_cron():
    from types import SimpleNamespace

    from ze_proactive.bootstrap import register_notification_jobs

    scheduler = MagicMock()
    settings = SimpleNamespace(
        config={"proactive": {"notifications": {"release_cron": "*/10 * * * *"}}}
    )
    register_notification_jobs(scheduler, settings, MagicMock(), AsyncMock())
    calls = {
        c.kwargs["job_id"]: c.kwargs for c in scheduler.add_cron_job.call_args_list
    }
    assert calls["quiet_hours_release"]["cron"] == "*/10 * * * *"
    assert calls["quiet_hours_release"]["catch_up"] is False
