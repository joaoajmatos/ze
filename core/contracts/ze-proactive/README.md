# ze-proactive

Job scheduling and push governance for Ze — background jobs, the interruption governor, and APScheduler wiring.

## Role in Ze

Proactive Ze runs on a schedule — morning briefings, calendar reminders, news fetches, goal checks, and correlation runs. `ze-proactive` provides the scheduler, job registration, and one send path for every proactive push.

### Key features

- `ProactiveScheduler` — APScheduler wrapper started at the `ze-api` lifespan, with cron catch-up after downtime
- `ProactiveJob` Protocol and the `@proactive_job` decorator, with cron and interval registration
- `ProactiveNotifier` — the single send path for proactive pushes; `push()` and `push_notification()` are gone
- Interruption governor — every push declares a class (`requested`, `accountability`, `discretionary`) and an urgency (`low`, `normal`, `high`), and one rule set decides deliver, hold, or suppress
- Quiet hours — a user setting; accountability and discretionary pushes are held silently and released together when quiet hours end
- Shared daily budget — only discretionary pushes claim it
- `PushLogStore` — tracks delivery and the shared budget claims

### Integration

Plugins register jobs in `ZePlugin.register_proactive_jobs()`. `ze-api` starts the scheduler after all plugins have started. Re-exported to plugin authors via `ze_sdk.proactive`.

`screen_resolvers.py` registers the `notification` screen resolver. It follows the notification's target one hop. `NotificationStore.get` reads one row.

## Interruption governor

`ProactiveNotifier.notify(kind, title, body, ...)` is the only proactive send path. Each `PushKind` names an event type and fixes its class, urgency, and source:

- `requested` — a reminder or calendar alert the user set. Always delivered, never budgeted, never held.
- `accountability` — a scheduled report or alert the user switched on. Never budgeted, held during quiet hours.
- `discretionary` — a nudge Ze chose to send. Claims the shared daily budget and is held during quiet hours.

`ze_proactive.governor.decide` is a pure function. It applies the rule in order: deliver `requested`; hold while quiet hours are active; deliver `accountability`; deliver `discretionary` only when the budget claim was won, else suppress. The outcome is one of `delivered`, `held`, `suppressed_budget`, `duplicate`, `deduped`, `failed`.

Quiet hours come from the single-row `interruption_settings` table, read by `InterruptionSettingsStore` and evaluated by `is_active(setting, now_utc)`. When quiet hours end, `QuietHoursReleaseJob` (`job_id = "quiet_hours_release"`, default cron `*/5 * * * *`) delivers each held row in urgency order, then one summary. A read failure counts as not quiet.

Cron jobs catch up after downtime. `JobRunStore` records each run in `proactive_job_runs`. On `start()`, `ProactiveScheduler` runs a job once when its scheduled time passed since its last run, within `catch_up_max_age_hours`.

## Responsibilities

| Module | What it provides |
|---|---|
| `scheduler.py` | `ProactiveScheduler` — thin wrapper around APScheduler with catch-up |
| `job.py` | `ProactiveJob` Protocol, `@proactive_job` registration |
| `types.py` | `PushKind`, `PushClass`, `Urgency`, `PushOutcome`, `BudgetStatus`, `QuietHoursSetting`, `JobRun`, `Notification` |
| `bootstrap.py` | `shared_push_budget` and `register_notification_jobs` (prune and quiet-hours release jobs) |
| `data_domain.py` | `interruption_data_domains` — export, import, and delete for the `interruption_settings` table |
| `staleness.py` | `is_stale` — the shared staleness helper |
| `screen_resolvers.py` | the `notification` screen resolver |
| `notifier.py` | `ProactiveNotifier` — the one send path; `notify`, `remaining_budget`, `deliver_held` |
| `governor.py` | `decide` — the pure deliver / hold / suppress rule |
| `push_kinds.py` | process-wide `PushKind` registry; `QUIET_HOURS_SUMMARY` |
| `quiet_hours.py` | `is_active` window check, `InterruptionSettingsStore` |
| `catchup.py` | `missed_fire_time` — the most recent missed cron fire time |
| `job_run_store.py` | `JobRunStore` — the last start and finish of each job |
| `notification_store.py` | `NotificationStore` — bell rows, held rows, unread counts |
| `push_log_store.py` | `PushLogStore` — Postgres-backed push delivery and budget log |
| `attention_budget.py` | shared daily budget claims `try_claim_shared` / `release_shared` |
| `jobs/prune_notifications.py` | `PruneNotificationsJob` — deletes old notification rows (default retention 90 days) |
| `jobs/release_held.py` | `QuietHoursReleaseJob` — releases held pushes when quiet hours end |

## Migrations

Branch `zpro`. `zpro001` creates `push_log`, `zpro002` creates `notifications`, `zpro003` adds the `push_log` idempotency key and its unique index, and `zpro005` adds `notifications.target_parent_id`. `zpro004_interruption_governor` adds the `notifications` columns (`push_class`, `urgency`, `format`, `actions`, `delivery`, `delivered_at`) and the `interruption_settings` and `proactive_job_runs` tables.

## Dependencies

![ze-proactive package dependencies](../../docs/diagrams/core/contracts/ze-proactive/dependencies.svg)

<sub>[Interactive version](../../docs/diagrams/core/contracts/ze-proactive/dependencies.html)</sub>

Third-party: `asyncpg`.

## Usage

Re-exported via `ze-sdk` for plugin job registration and push kinds:

```python
from ze_sdk.proactive import ProactiveScheduler, ProactiveJob, proactive_job, PushKind

MORNING_BRIEF = PushKind("morning_brief", "accountability", "normal", "personal")
```

Sites call `await notifier.notify(kind, title, body, budget_key=...)`. Plugins register jobs in `ZePlugin.register_proactive_jobs()`; `ze-api` starts the scheduler at startup.

## Attention budget

`budget_status(push_log, max_per_day)` is the one count of the rolling 24-hour window. `within_budget`, `ProactiveNotifier.remaining_budget` and `ProactiveNotifier.budget_status` all call it, so the claim path and the REST route (`GET /api/v0/notifications/budget`) never disagree. `PushLogStore.window_sent_at` runs the one window query. `JobRunStore.list_runs` lists the last run of each job and raises on a store failure. `NotificationStore.list_page` filters by `delivery`, `push_class` and `since`.

## Testing

From the repo root:

```bash
make test-proactive
```

See [docs/testing.md](../../docs/testing.md).
