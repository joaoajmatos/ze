# Contract: Catch-up

## `ze_proactive.catchup.missed_fire_time`

```python
def missed_fire_time(cron: str, last_run_at: datetime, now: datetime, tz: tzinfo) -> datetime | None
```

Returns the latest fire time `t` of `CronTrigger.from_crontab(cron, timezone=tz)` with `last_run_at < t <= now`, else `None`. Aware datetimes only; a naive datetime raises `CatchUpError(ZeError)` (in `ze_proactive/errors.py`). Iteration capped at 10 000 steps (logs `catchup_iteration_cap`, returns the last computed time).

## `JobRunStore` (`ze_proactive/job_run_store.py`)

- `record_start(job_id) -> None` — upsert `last_started_at=now(), last_finished_at=NULL, last_status='running'`
- `record_finish(job_id, status: Literal["ok","error"]) -> None`
- `get_all() -> dict[str, JobRun]`

All methods log and swallow store errors (a job never fails because its run could not be recorded).

## `ProactiveScheduler`

```python
ProactiveScheduler(run_store: JobRunStore | None = None, clock=…)
register(job, cron, *, catch_up=True, catch_up_max_age_hours=None)
add_cron_job(fn, cron, job_id, *, catch_up=True, catch_up_max_age_hours=None)
```

- Every cron job is added with `misfire_grace_time=None`, `coalesce=True`, `max_instances=1`, and wrapped: `record_start` → `await fn()` → `record_finish("ok"|"error")` (exception re-raised after recording).
- `start()`: loads `get_all()`; for each registered job in registration order with `catch_up`, a run row, `missed_fire_time(...)` not None, and (if set) `now - missed <= catch_up_max_age_hours`: add a one-off `DateTrigger(now + 5s × i)` job id `"{job_id}:catchup"` with `misfire_grace_time=None`. Logs `proactive_job_catch_up` (job_id, missed_at).
- Without a run store: no recording, no catch-up (tests, seed).

## `WorkflowScheduler.start()`

After `recover_stale`, for each enabled scheduled workflow with at least one execution: `missed_fire_time(workflow.schedule, latest.started_at, now, scheduler tz)`; if not None → `await self.trigger_now(workflow.id)` and log `workflow_catch_up`. `schedule_job`, `schedule_at`, `_add_job` pass `misfire_grace_time=None`.

## `CalendarReminderService.replay_unsent()`

For each unsent reminder: `fire_at <= now` → `asyncio.create_task(self.fire_reminder(r.id, late_from=r.fire_at))`; else schedule as today. `fire_reminder(reminder_id, late_from=None)` appends ` (late, was due HH:MM)` (user timezone from `Settings.timezone`) when `late_from` is set.
