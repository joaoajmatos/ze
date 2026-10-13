# Research: Interruption Governor (part 1)

All findings verified against `main` 0b9845b1 on 2026-10-12.

## R1 — Where the governor lives

- **Decision**: Inside `ProactiveNotifier.notify` in `core/contracts/ze-proactive`. The pure rule is `ze_proactive/governor.py::decide`; the notifier does the I/O (budget claim, settings read, row write, interface call).
- **Rationale**: `ze-proactive` already owns the transport wrapper, `notifications` (bell) and `push_log` (budget). Every push site already holds a `ProactiveNotifier`. A wrapper class around the notifier would leave the old methods reachable (two paths).
- **Alternatives**: a new `ze-interrupt` package (new dependency edges for nine packages, no gain); governing in `NativeAppInterface` (ze-api; plugins' intent—class and budget key—would not reach it).

## R2 — Hold semantics during quiet hours and release

- **Decision** (Q1 = A, user 2026-10-13): a held push becomes a `notifications` row with `delivery='held'` and a silent `notification` frame. No chat message, no ntfy. `QuietHoursReleaseJob` (cron `*/5 * * * *`) runs when quiet hours are not active: it delivers each held row through the interface with `buzz=False` (chat message + action frames + notification frame, same as a normal delivery), orders them by urgency then age, marks them `released`, then sends one `quiet_hours_summary` notification with `buzz=True` at the highest held urgency.
- **Rationale**: Nothing is lost; actions (Start goal, Add contact) survive; one buzz instead of N; restart-safe (the job reads rows, not memory), so a server that was down at the end of quiet hours releases on its first run after start.
- **Why the row stores actions and format**: today `notify()` persists only title/body; a held push must be replayable as it would have been delivered. `zpro004` adds `format`, `actions JSONB`, `urgency`, `push_class`.
- **Alternatives**: drop (bell only) — users lose approval requests; briefing queue — couples to a plugin job, once a day, lost when the briefing is off.

## R3 — Budget generalisation and arbitration

- **Decision**: keep `ATTENTION_PUSH_EVENT_KEY` rows in `push_log` and the `(event_type, idempotency_key)` unique index (`zpro003`). `try_claim_shared(push_log, budget_key, max_per_day, payload=None)` takes a free string. Discretionary `notify()` claims first; a lost claim on an existing key is `duplicate`; a full budget is `suppressed_budget`. A failed delivery releases the claim. Held pushes keep their claim.
- **Arbitration**: `AttentionArbitrationJob` keeps ranking loops and hypotheses with `PriorityView.rank_subset`, but no longer claims. It asks `notifier.remaining_budget()` (0 → return) and calls `LoopSurfacer.send(loop)` / `CorrelationPushCandidateSource.send(h)`, which now return `PushOutcome | None` (`None` when the loop is no longer drifting). It stops at the first `delivered` or `held`, continues on `duplicate`/`None`/`failed`, and stops on `suppressed_budget`.
- **Budget keys** for other sites are listed in the spec inventory; date-scoped keys (`stuck_goals:<date>`, `finance_stale:<account>:<date>`) use the server-local date (`date.today()`), which is enough for a 24 h idempotency window.
- **Alternatives**: one budget per class (no: D4 says the budget is for discretionary only); ranking all discretionary sources now (needs data; 178–179).

## R4 — Quiet-hours time math

- **Decision**: pure `is_active(setting, now_utc) -> bool`. Convert `now_utc` to the stored `ZoneInfo`, take local wall time `t`. If `start < end`: active iff `start <= t < end`. If `start > end` (across midnight): active iff `t >= start or t < end`. `start == end` is rejected at write time. DST: wall-clock comparison means a 23:00–08:00 window is 8 or 10 real hours on change nights, which is what a user expects; a skipped local time simply never matches, so the window ends at the first valid local time after `end`.
- **Settings read**: `InterruptionSettingsStore.get()` per push (single-row primary-key read). A read error → treated as off, warning logged (never drop on a settings error).
- **Server `TIMEZONE`**: not used for quiet hours; the stored zone is authoritative. The form prefills the browser zone.

## R5 — Catch-up for missed runs

- **APScheduler 3.11 facts**: `AsyncIOScheduler` uses an in-memory job store; `misfire_grace_time` defaults to 1 second for jobs added without it, so a run whose time passes while the process is suspended (laptop sleep) is skipped with "Run time of job … was missed". `misfire_grace_time=None` means no limit; with `coalesce=True` a late cron job runs once. A `DateTrigger` job added with a past `run_date` is also dropped as missed under the 1-second grace — this is why `CalendarReminderService.replay_unsent` silently loses overdue calendar reminders (user reminders avoid it by firing overdue ones with `asyncio.create_task` in `ze_calendar/plugin.py`).
- **Decision**: (1) `ProactiveScheduler` wraps each cron job to record `last_started_at`/`last_finished_at`/`last_status` in `proactive_job_runs` (best-effort; a store error is logged and never blocks the job), registers with `misfire_grace_time=None, coalesce=True`, and on `start()` schedules one run for each job with `catch_up=True`, a recorded run, and `missed_fire_time(cron, last_started_at, now)` not None and within `catch_up_max_age_hours` (if set). Runs are staggered 5 s apart via `DateTrigger(now + 5s × i)` with `misfire_grace_time=None`. (2) `WorkflowScheduler.start()` does the same per workflow using its latest execution's `started_at` and calls `trigger_now`. (3) `replay_unsent` fires overdue calendar reminders immediately.
- **`missed_fire_time`**: iterate `CronTrigger.from_crontab(cron, timezone=tz).get_next_fire_time(prev, cursor)` from `last_run_at` while the next time is `<= now`; return the last one. Bounded loop (stop after 10 000 iterations — a `* * * * *` job down for a week is 10 080 minutes, so cap returns the latest computed time; log `catchup_iteration_cap`). Scheduler timezone: `AsyncIOScheduler().timezone` (local), passed explicitly.
- **First start**: no row → no catch-up; the first scheduled run creates the row.
- **Briefing age limit**: `proactive.briefing.catch_up_max_age_hours: 6` so a missed 08:00 briefing does not arrive at 23:00.
- **Alternatives**: APScheduler `SQLAlchemyJobStore` (adds SQLAlchemy and a sync driver; the project uses asyncpg raw SQL); catching up every missed run (spams on long downtime).

## R6 — Enforcing one send path

- **Decision**: (a) delete `ProactiveNotifier.push`/`push_notification`; (b) `PushKind` registry with a composition-root test (`apps/ze-api/tests/test_push_inventory.py`) that imports every package's `push_kinds` module (via plugin discovery + core imports) and compares `registered_push_kinds()` to an expected dict mirroring the spec inventory; (c) an AST test in the same file that walks `core/`, `plugins/`, `apps/ze-api/ze_api/` (not tests) and fails on any `.push(` attribute call whose receiver name contains `notifier` or `interface`, except in `ze_proactive/notifier.py` and `ze_api/interface/native.py`. False positives (`self._signals.push(msg)` in messenger, `signal_source.push` in news) are excluded because their receivers do not match.

## R7 — Contested classifications (Q4 = A, user 2026-10-13)

- Briefing, weekly accountability report, weekly goal narrative → `accountability`: the user enabled them in config and they report on the user's own state; budgeting them would let a scheduled report starve a loop nudge or vice versa.
- Messenger inbound relay → `discretionary`: Ze decides which inbound messages to relay. Today it never sends (TypeError), so this is not a regression.
- Stuck goals → `discretionary`: a nudge, not a report of an event; it already had `SourceKind "goal"` reserved in Phase 123.
- `calendar_reminders_scheduled` (A15) → `accountability`, low: it reports an action Ze took for the user.
- Approval requests (A1, A5, A10) → `accountability`, high; they wait in quiet hours (Q2). The timeout notice (A2) is `low`.

## R8 — Web placement (FSD)

- `entities/quiet-hours/api/useQuietHoursQuery.ts` (query key `["quiet-hours"]`) and `useUpdateQuietHoursMutation.ts` (invalidates `["quiet-hours"]` and the notifications queries), exported from `entities/quiet-hours/index.ts`.
- `widgets/quiet-hours-settings/ui/QuietHoursSettings.tsx`: switch, two `Input type="time"`, timezone `Input` with `list` of `Intl.supportedValuesOf("timeZone")` when available, read-only budget line, status line (`active_now`, `held_count`), field errors from the 422 `detail`. Mounted inside the existing "Notifications" block of `SettingsWorkspace.tsx`, above the ntfy button.
- Bell label: `widgets/notification-bell/ui/NotificationBell.tsx` maps `delivery` → label; no new entity.
