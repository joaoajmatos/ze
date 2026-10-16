from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_proactive.scheduler import ProactiveScheduler
from ze_proactive.types import JobRun


def _now():
    return datetime.now(timezone.utc)


def _run(job_id, started_ago: timedelta) -> JobRun:
    return JobRun(job_id, _now() - started_ago, _now() - started_ago, "ok")


def _store(runs: dict[str, JobRun] | None = None):
    store = MagicMock()
    store.get_all = AsyncMock(return_value=runs or {})
    store.record_start = AsyncMock()
    store.record_finish = AsyncMock()
    return store


def _job_ids(sched: ProactiveScheduler) -> list[str]:
    return [j.id for j in sched._scheduler.get_jobs()]


async def _started(sched: ProactiveScheduler):
    await sched.start()
    try:
        return {j.id: j for j in sched._scheduler.get_jobs()}
    finally:
        await sched.stop()


async def test_missed_job_gets_one_catchup():
    sched = ProactiveScheduler(
        run_store=_store({"a": _run("a", timedelta(minutes=10))})
    )
    sched.add_cron_job(AsyncMock(), "* * * * *", "a")
    jobs = await _started(sched)
    assert "a:catchup" in jobs and jobs["a:catchup"].misfire_grace_time is None


async def test_no_run_row_means_no_catchup():
    sched = ProactiveScheduler(run_store=_store({}))
    sched.add_cron_job(AsyncMock(), "* * * * *", "a")
    assert "a:catchup" not in await _started(sched)


async def test_no_run_store_means_no_catchup():
    sched = ProactiveScheduler()
    sched.add_cron_job(AsyncMock(), "* * * * *", "a")
    assert "a:catchup" not in await _started(sched)


async def test_not_missed_means_no_catchup():
    sched = ProactiveScheduler(run_store=_store({"a": _run("a", timedelta(seconds=0))}))
    sched.add_cron_job(AsyncMock(), "0 8 * * *", "a")
    assert "a:catchup" not in await _started(sched)


async def test_catch_up_false_is_skipped():
    sched = ProactiveScheduler(
        run_store=_store({"a": _run("a", timedelta(minutes=10))})
    )
    sched.add_cron_job(AsyncMock(), "* * * * *", "a", catch_up=False)
    assert "a:catchup" not in await _started(sched)


async def test_max_age_limit_is_honoured():
    # last fire was ~10 min ago; limit of 1 minute rejects it, 1 hour accepts it.
    runs = {"a": _run("a", timedelta(hours=3))}
    sched = ProactiveScheduler(run_store=_store(runs))
    sched.add_cron_job(AsyncMock(), "0 * * * *", "a", catch_up_max_age_hours=0.0001)
    jobs = await _started(sched)
    assert "a:catchup" not in jobs

    sched = ProactiveScheduler(run_store=_store(runs))
    sched.add_cron_job(AsyncMock(), "0 * * * *", "a", catch_up_max_age_hours=2)
    assert "a:catchup" in await _started(sched)


async def test_catchups_are_staggered_five_seconds():
    runs = {i: _run(i, timedelta(minutes=10)) for i in ("a", "b")}
    sched = ProactiveScheduler(run_store=_store(runs))
    sched.add_cron_job(AsyncMock(), "* * * * *", "a")
    sched.add_cron_job(AsyncMock(), "* * * * *", "b")
    jobs = await _started(sched)
    gap = jobs["b:catchup"].next_run_time - jobs["a:catchup"].next_run_time
    assert gap == timedelta(seconds=5)


async def test_wrapper_records_ok():
    store = _store()
    fn = AsyncMock()
    sched = ProactiveScheduler(run_store=store)
    sched.add_cron_job(fn, "0 8 * * *", "a")
    await sched._scheduler.get_job("a").func()
    fn.assert_awaited_once()
    store.record_start.assert_awaited_once_with("a")
    store.record_finish.assert_awaited_once_with("a", "ok")


async def test_wrapper_records_error_and_reraises():
    store = _store()
    fn = AsyncMock(side_effect=RuntimeError("boom"))
    sched = ProactiveScheduler(run_store=store)
    sched.add_cron_job(fn, "0 8 * * *", "a")
    with pytest.raises(RuntimeError):
        await sched._scheduler.get_job("a").func()
    store.record_finish.assert_awaited_once_with("a", "error")


async def test_cron_jobs_have_no_misfire_limit():
    sched = ProactiveScheduler()
    sched.add_cron_job(AsyncMock(), "0 8 * * *", "a")
    job = sched._scheduler.get_job("a")
    assert job.misfire_grace_time is None and job.coalesce and job.max_instances == 1


async def test_a_parked_write_escaping_a_job_is_logged_and_not_raised():
    from ze_agents.errors import LoopParked
    from ze_agents.park import ParkedLoop

    store = _store()
    sched = ProactiveScheduler(run_store=store)
    job = AsyncMock(side_effect=LoopParked(ParkedLoop("a", [], [], 0)))
    sched.add_cron_job(job, "* * * * *", "a")
    registered = sched._registered["a"]

    await registered.run()

    job.assert_awaited_once()
    store.record_finish.assert_awaited_once_with("a", "error")


async def test_wrapper_enters_job_context_before_the_job_runs():
    order: list[str] = []
    fn = AsyncMock(side_effect=lambda: order.append("job"))
    sched = ProactiveScheduler(job_context=lambda job_id: order.append(f"ctx:{job_id}"))
    sched.add_cron_job(fn, "0 8 * * *", "a")
    await sched._scheduler.get_job("a").func()
    assert order == ["ctx:a", "job"]


async def test_global_catch_up_switch_off_skips_every_catchup():
    runs = {"a": _run("a", timedelta(minutes=10))}
    sched = ProactiveScheduler(run_store=_store(runs), catch_up=False)
    sched.add_cron_job(AsyncMock(), "* * * * *", "a")
    assert "a:catchup" not in await _started(sched)


async def test_global_catch_up_switch_on_by_default():
    runs = {"a": _run("a", timedelta(minutes=10))}
    sched = ProactiveScheduler(run_store=_store(runs))
    sched.add_cron_job(AsyncMock(), "* * * * *", "a")
    assert "a:catchup" in await _started(sched)


async def test_configured_per_job_max_age_applies():
    runs = {"a": _run("a", timedelta(hours=3))}
    sched = ProactiveScheduler(
        run_store=_store(runs), catch_up_max_age_hours={"a": 0.0001}
    )
    sched.add_cron_job(AsyncMock(), "0 * * * *", "a")
    assert "a:catchup" not in await _started(sched)


async def test_configured_max_age_leaves_other_jobs_alone():
    runs = {i: _run(i, timedelta(hours=3)) for i in ("a", "b")}
    sched = ProactiveScheduler(
        run_store=_store(runs), catch_up_max_age_hours={"a": 0.0001}
    )
    sched.add_cron_job(AsyncMock(), "0 * * * *", "a")
    sched.add_cron_job(AsyncMock(), "0 * * * *", "b")
    jobs = await _started(sched)
    assert "a:catchup" not in jobs and "b:catchup" in jobs


async def test_explicit_registration_max_age_wins_over_config():
    runs = {"a": _run("a", timedelta(hours=3))}
    sched = ProactiveScheduler(
        run_store=_store(runs), catch_up_max_age_hours={"a": 0.0001}
    )
    sched.add_cron_job(AsyncMock(), "0 * * * *", "a", catch_up_max_age_hours=2)
    assert "a:catchup" in await _started(sched)
