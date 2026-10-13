# Implementation Plan: Interruption Governor (part 1)

**Branch**: `177-interruption-governor` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/177-interruption-governor/spec.md`

## Summary

Put every proactive push behind one rule-based governor inside `ProactiveNotifier` (`core/contracts/ze-proactive`). Each push site declares a module-level `PushKind` (class `requested` / `accountability` / `discretionary`, urgency `low` / `normal` / `high`). `notify()` becomes the only send path (hard cut: `push()` and `push_notification()` are deleted). Requested pushes always deliver; during quiet hours everything else is stored as a silent bell row and released as a batch by a 5-minute job; discretionary pushes claim the shared daily budget (generalised to free-form budget keys, default 5). Quiet hours are a single-row table with `GET`/`PUT /api/v0/notifications/quiet-hours`, a regenerated client and a form on the Settings page. `ProactiveScheduler` records job runs and catches up once on start; the workflow scheduler and the calendar reminder replay get the same treatment. One migration, `zpro004`.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 + React 18 (ze-web)

**Primary Dependencies**: FastAPI, asyncpg, APScheduler 3.11.2 (`CronTrigger`, `misfire_grace_time`), `zoneinfo`; ze-web: TanStack Query, `@myguyze/ze-client` (hey-api codegen), `shared/ui` components

**Storage**: Postgres; `ze-proactive` chain `zpro` (`zpro004`): new columns on `notifications`, new tables `interruption_settings` and `proactive_job_runs`

**Testing**: pytest (`asyncio_mode=auto`, `AsyncMock` pools, fake interface and clock); vitest + Testing Library for ze-web

**Target Platform**: single-user server (often a laptop) and the web client

**Project Type**: monorepo web service + SPA

**Performance Goals**: `notify()` adds at most two single-row reads (settings, budget count) per push; the release job is O(held rows)

**Constraints**: no LLM or System One call; no new graph node; new plugin code imports `PushKind` through `ze_sdk.proactive`; no compatibility shims (Principle VIII)

**Scale/Scope**: 30 inventory rows (31 kinds) in 9 packages; 2 REST routes; 2 new web slices; 1 migration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First Development** — PASS. This spec, governed by `executive-function.md` D4.
- **II. Single-User Model** — PASS. One settings row (`id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id)`), one budget.
- **III. Layered Package Architecture** — PASS. Governor, kinds, quiet hours and job runs live in `ze-proactive`, which already owns `notifications` and `push_log`. `PushClass` and `Urgency` are closed core enums mandated by decision D4, not plugin vocabulary. `event_type` and `source` stay free strings declared by each package in its own `push_kinds.py`. No new package edge: every caller already depends on `ze-proactive` directly or through `ze-sdk`.
- **IV. Typed, Explicit Python** — PASS. Dataclasses in `ze_proactive/types.py`; Pydantic only in `ze_api/api/schemas.py`; `PushPolicyError(ZeError)`; settings store and run store arrive by constructor injection.
- **V. Test Discipline** — PASS. Unit tests per package with fakes; acceptance pytest (SC-001); vitest for the form and the bell label.
- **VI. Explicit Persistence** — PASS. Raw-SQL Alembic `zpro004` in `ze-proactive`.
- **VII. One LLM Gateway, Local Embeddings** — PASS (no model use).
- **VIII. Pre-v1 Hard Cuts** — PASS. `push()`/`push_notification()` deleted, `SourceKind` deleted, `try_claim_shared` signature changed, `LoopSurfacer.claim_push`/`release_push_claim` deleted (no non-test callers), existing notification rows backfilled by the migration (no dual read).

Post-design re-check: PASS (no change).

## Blast radius

graphify `affected --depth 2` on the graph at `main` 0b9845b1, plus grep where the graph has no unique node (`ProactiveNotifier`, `WorkflowScheduler`).

| Changed symbol | Callers by package |
|---|---|
| `ProactiveNotifier.push` / `push_notification` / `notify` | **ze-api**: `api/websocket/confirmation.py` (A1, A2), `container.py` (A3, construction), `interface/native.py`; **ze-automation**: `bootstrap.py` (A4, `wire_goal_executor_push`), `agents/goals/tools.py` (A5, D5), `goals/executor.py` (A6–A10, D6), `jobs/{cost_anomaly,accountability,goal_narrative,stuck_goals,goal_suggestion}.py`; **ze-worldstate**: `surfacing.py` (D1); **ze-correlation**: `push.py` (D2); **ze-memory**: `dream/job.py` (D7); **ze-personal**: `jobs/{briefing,insights,contacts}.py`; **ze-calendar**: `reminders/{store,calendar}.py`; **ze-finance**: `jobs/recurring.py`; **ze-messenger**: `inbound/processor.py`; **ze-sdk**: `proactive.py` re-export |
| `try_claim_shared` / `release_shared` | **ze-priority**: `arbitration.py` `run()`; **ze-worldstate**: `surfacing.py` `claim_push()` / `release_push_claim()` (no non-test callers); tests: `ze-proactive/tests/test_attention_budget.py` |
| `SourceKind` | `ze_proactive/attention_budget.py` only (ze-priority keeps its own `source_kind` literal) |
| `ProactiveScheduler` | **ze-api**: `compose.py`, `container.py` (construction L764, start L911), `seed.py`; **ze-proactive** `bootstrap.py`; `bootstrap.py` in **ze-automation**, **ze-correlation**, **ze-memory**, **ze-worldstate**, **ze-skills**; `plugin.py` in **ze-messenger**, **ze-personal**, **ze-prospecting**, **ze-finance**, **ze-news**, **ze-calendar**. The new parameters are keyword-only with defaults, so only `container.py` (run store) and `ze-personal` (briefing age limit) change. |
| `AttentionArbitrationJob` | **ze-api**: `compose.py` L79 (constructor: drops `push_log`, `max_pushes_per_day`; gains `notifier`), `container.py`; `ze-priority/tests/test_arbitration.py` (rewritten) |
| `Notification` (`ze_agents.interface.types`) | `NativeAppInterface`; fakes in ze-api `tests/api/test_ws_conformance.py`, `tests/interface/test_native.py`. Additive field. |
| `WorkflowScheduler.start` / `schedule_at` | **ze-automation** `workflow/scheduler.py`; callers in **ze-calendar** `plugin.py` (user reminders) and `reminders/calendar.py` |
| `NotificationItem` (REST) | `ze_api/api/routes/notifications.py`; ze-web `entities/notification`, `widgets/notification-bell` |

Test files that mock the removed methods (grep) and must be migrated: ze-api `tests/agents/test_bootstrap.py`, `tests/api/test_workspace_followthrough.py`, `tests/api/test_ws_conformance.py`, `tests/interface/test_native.py`; ze-automation `tests/goal_agent/{test_create_goal_convergence,test_goal_agent,test_goal_tools}.py`, `tests/proactive_jobs/{test_goal_narrative,test_goal_suggestion,test_stuck_goals}.py`; ze-correlation `tests/test_push.py`; ze-worldstate `tests/test_surfacing.py`; ze-proactive `tests/{test_attention_budget,test_notifier,test_imports}.py`; ze-calendar `tests/jobs/test_reminders.py`; ze-messenger `tests/test_inbound_polling_job.py`; ze-personal `tests/jobs/{test_briefing,test_contact_review,test_insights}.py`; ze-priority `tests/test_arbitration.py`.

**Overlap with sibling floors.** Phase 170 edits `ze_priority/arbitration.py` (`__init__`, loop settings into `eligible_candidates`), `ze_worldstate/surfacing.py` (`passes_push_bar`, deletes `inline_candidates`), `ze_correlation/push.py` (`eligible_candidates` enabled / dry_run), `compose.py` (arbitration arguments) and `config.yaml` (`worldstate`, `correlation.push`). 177 edits `arbitration.run` and its constructor, `LoopSurfacer.send` (and deletes `claim_push`/`release_push_claim`), `CorrelationPushCandidateSource.send`, `compose.py` (arbitration arguments) and `config.yaml` (`proactive.budget`, `proactive.briefing`). The phase that lands second rebases and resolves; T001 checks which has landed. Phases 169, 171 and 172 do not touch push sites.

## Project Structure

### Documentation (this feature)

```text
specs/phases/177-interruption-governor/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── governor-api.md        # PushKind / notify / PushOutcome / decide
│   ├── quiet-hours-rest.md    # GET/PUT /api/v0/notifications/quiet-hours, NotificationItem delta
│   └── catch-up.md            # missed_fire_time, JobRunStore, scheduler start rule
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
core/contracts/ze-proactive/ze_proactive/
├── types.py                 # + PushClass, Urgency, PushKind, PushOutcome, Delivery, QuietHoursSetting, JobRun; NotificationRow/Notification gain push_class, urgency, delivery
├── errors.py                # NEW: PushPolicyError(ZeError)
├── push_kinds.py            # NEW: registry, registered_push_kinds(); QUIET_HOURS_SUMMARY kind
├── governor.py              # NEW: decide(), Decision
├── quiet_hours.py           # NEW: is_active() (pure), InterruptionSettingsStore (asyncpg)
├── notifier.py              # notify() is the governor entry; push()/push_notification() deleted; remaining_budget(); deliver_held()
├── attention_budget.py      # budget_key: str; SourceKind deleted
├── notification_store.py    # create() takes push_class/urgency/format/actions/delivery; list_held(); mark_released(); mark_failed(); count_held()
├── catchup.py               # NEW: missed_fire_time()
├── job_run_store.py         # NEW: JobRunStore
├── scheduler.py             # run-recording wrapper, misfire_grace_time=None, catch-up in start()
├── jobs/release_held.py     # NEW: QuietHoursReleaseJob
├── bootstrap.py             # registers release job; budget default 5
└── migrations/versions/zpro004_interruption_governor.py   # NEW

core/contracts/ze-agents/ze_agents/interface/types.py        # Notification.urgency: Urgency; + buzz: bool = True
packages/ze-sdk/ze_sdk/proactive.py                          # re-export PushKind, PushOutcome, PushClass, Urgency

core/arbitration/ze-priority/ze_priority/arbitration.py      # no claim; remaining_budget() gate; outcome-driven loop
core/cognition/ze-worldstate/ze_worldstate/push_kinds.py     # NEW: LOOP_DRIFT
core/cognition/ze-worldstate/ze_worldstate/surfacing.py      # send() → notify(LOOP_DRIFT, budget_key=f"loop:{id}") → PushOutcome
core/cognition/ze-correlation/ze_correlation/push_kinds.py   # NEW: HYPOTHESIS
core/cognition/ze-correlation/ze_correlation/push.py         # send() → notify(HYPOTHESIS, budget_key=f"hypothesis:{id}") → PushOutcome
core/cognition/ze-memory/ze_memory/{push_kinds.py (NEW), dream/job.py}   # D7
core/automation/ze-automation/ze_automation/
├── push_kinds.py            # NEW: A4–A13, D3–D6
├── bootstrap.py             # A4; wire_goal_executor_push binds one notify callable
├── agents/goals/tools.py    # A5, D5
├── goals/executor.py        # A6–A10, D6 (await fix); `_push` + `_notify` collapse to `_notify`
├── jobs/{cost_anomaly,accountability,goal_narrative,stuck_goals,goal_suggestion}.py
└── workflow/scheduler.py    # catch-up in start(); misfire_grace_time=None

plugins/ze-calendar/ze_calendar/{push_kinds.py, reminders/store.py, reminders/calendar.py}     # R1, R2, A15, overdue replay
plugins/ze-personal/ze_personal/{push_kinds.py, jobs/briefing.py, jobs/insights.py, jobs/contacts.py, plugin.py}
plugins/ze-finance/ze_finance/{push_kinds.py, jobs/recurring.py}
plugins/ze-messenger/ze_messenger/{push_kinds.py, inbound/processor.py}

apps/ze-api/ze_api/
├── push_kinds.py            # NEW: A1, A2, A3
├── api/websocket/confirmation.py, container.py, compose.py
├── interface/native.py      # buzz flag; quiet-hours check on ntfy hops; urgency map with low
├── api/routes/notifications.py, api/schemas.py, api/dependencies.py
└── config/config.yaml       # budget 5, briefing catch_up_max_age_hours

apps/ze-web/src/
├── entities/quiet-hours/{api/useQuietHoursQuery.ts, api/useUpdateQuietHoursMutation.ts, index.ts}
├── widgets/quiet-hours-settings/{ui/QuietHoursSettings.tsx, ui/QuietHoursSettings.test.tsx, index.ts}
├── widgets/settings-workspace/ui/SettingsWorkspace.tsx     # mount in the Notifications section
└── widgets/notification-bell/ui/NotificationBell.tsx (+ .test.tsx)   # delivery label
packages/ze-client/src/generated/*                           # make codegen
```

**Structure Decision**: Governor in `ze-proactive` (owner of the transport, the bell table and the push log). Each package keeps its own `push_kinds.py`, so core holds no plugin event names (Principle III). The composition-root test in `apps/ze-api/tests/` checks the full inventory.

## Phase 0 / Phase 1 outputs

- [research.md](research.md): R1 where the governor lives; R2 hold and release; R3 budget generalisation and arbitration; R4 quiet-hours time math; R5 catch-up; R6 enforcing one send path; R7 contested classifications; R8 web placement.
- [data-model.md](data-model.md): `PushKind`, `PushOutcome`, `Delivery`, `notifications` delta, `interruption_settings`, `proactive_job_runs`.
- [contracts/](contracts/): Python governor API, REST, catch-up.
- [quickstart.md](quickstart.md): manual acceptance run against `make dev`.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Per-package `push_kinds.py` + registry | One reviewable inventory per package; the composition-root test catches unclassified pushes | A central core table of event names puts plugin vocabulary in core (Principle III) |
| Silent bell rows for held and suppressed pushes | The user can see what Ze kept back (governance honesty, the D7 weekly check) | Dropping silently makes "an alert I wanted but did not get" invisible |
