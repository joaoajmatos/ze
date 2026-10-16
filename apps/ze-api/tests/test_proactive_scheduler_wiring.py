"""The shell builds the proactive scheduler from config: attribution context and catch-up controls."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from ze_api.compose import build_proactive_scheduler
from ze_core.telemetry.context import get_cost_context
from ze_proactive.types import JobRun


def _settings(proactive: dict | None = None):
    return SimpleNamespace(config={"proactive": proactive or {}})


def _store(job_id: str, started_ago: timedelta):
    now = datetime.now(timezone.utc)
    run = JobRun(job_id, now - started_ago, now - started_ago, "ok")
    store = MagicMock()
    store.get_all = AsyncMock(return_value={job_id: run})
    store.record_start = AsyncMock()
    store.record_finish = AsyncMock()
    return store


async def _jobs(sched):
    await sched.start()
    try:
        return {j.id for j in sched._scheduler.get_jobs()}
    finally:
        await sched.stop()


async def test_jobs_run_under_a_proactive_cost_context():
    seen = []

    async def job():
        seen.append(get_cost_context())

    sched = build_proactive_scheduler(_settings(), run_store=None)
    sched.add_cron_job(job, "0 8 * * *", "news_fetch")
    await sched._scheduler.get_job("news_fetch").func()

    assert (seen[0].flow_type, seen[0].agent, seen[0].session_id) == (
        "proactive",
        "news_fetch",
        "job:news_fetch",
    )


async def test_catch_up_defaults_on():
    sched = build_proactive_scheduler(
        _settings(), run_store=_store("a", timedelta(minutes=10))
    )
    sched.add_cron_job(AsyncMock(), "* * * * *", "a")
    assert "a:catchup" in await _jobs(sched)


async def test_catch_up_false_in_config_turns_it_off():
    sched = build_proactive_scheduler(
        _settings({"catch_up": False}), run_store=_store("a", timedelta(minutes=10))
    )
    sched.add_cron_job(AsyncMock(), "* * * * *", "a")
    assert "a:catchup" not in await _jobs(sched)


async def test_per_job_max_age_comes_from_config():
    sched = build_proactive_scheduler(
        _settings({"catch_up_max_age_hours": {"a": 0.0001}}),
        run_store=_store("a", timedelta(hours=3)),
    )
    sched.add_cron_job(AsyncMock(), "0 * * * *", "a")
    assert "a:catchup" not in await _jobs(sched)
