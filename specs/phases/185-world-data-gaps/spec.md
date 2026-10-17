# Feature Specification: World Data Gaps (B2)

**Feature Branch**: `185-world-data-gaps`

**Created**: 2026-10-17

**Status**: Implemented

**Input**: Maestro brief 2026-10-17, backend floor B2: overhaul plan section d, gaps 3, 4, 6, 12. Planned in full on 2026-10-17 at the user's "keep going".

**Governed by**: `specs/arch/claim-topology.md`, `specs/arch/pre-v1-hard-cuts.md`, `DESIGN.md` ("a value the API does not expose is omitted, not faked"). Prior phases: 57 (correlation hypotheses), 109–111 (loops, claim decay), 172 (corroboration), 173 (`open_loops.reminder_id`), 177 (interruption governor, `push_log`, `proactive_job_runs`, `notifications.delivery`), 13/22 (reminders).

**Depends on**: 184 (B1) for `ClaimPosture.confidence_from` and the composer's loop postures, which this phase fills for loops, and for the 184 notification fields (`target_parent_id`) that this phase's notification list changes sit next to. The floor branches from `main` after 184 lands. Should land before 186 (World), 189 (Mind) and 190 (Governance); each of those degrades gracefully (omits the value) without it.

**Doctrine functions served**: executive function (reminders as deadlines on concerns, honest confidence movement), reflection (hypotheses as claims the user can inspect and dismiss), governance (the interruption budget is visible).

---

## Clarifications

### Session 2026-10-17 (planning against the code)

The spec-level draft assumed things the code does not do. The plan follows the code; these corrections are binding.

- **The budget is a rolling 24-hour window, not a calendar day.** `within_budget` counts `push_log` claims with `sent_at > now() - 24 h`. The route reports that rule (`used`, `window_hours`, `next_slot_at`); it does not invent a "today" or a timezone boundary. Changing the governor to a calendar day is out of scope.
- **`push_log` records budget claims, not outcomes.** What happened to each push (delivered, held, released, suppressed, failed) is `notifications.delivery` (zpro004). The "push log" view is `listNotifications` with `delivery`, `push_class` and `since` filters. There is no `listPushLog` route. A deduplicated push never creates a notification row, so it is not listed (it was never an event the user missed).
- **`proactive_job_runs` keeps one row per job (the last run).** The route lists the last run per job (`listProactiveJobRuns`), not a run history. No history table is added until a screen needs more than "what ran since you left".
- **Loop confidence does not decay over time.** It changes only on evidence events: contradiction (`decay.cascade_from_evidence`), corroboration, `track_loop` reinforcement, declaration and confirmation (`stamp_declared`), promotion. So the honest "from" value is the confidence before the last change (`confidence_prior`, with `confidence_changed_at`), and it can be lower than the current value (corroboration raises it). `ClaimPosture.confidence_from` for loops means "the value before the last change"; the 184 contract line is amended when this phase lands.
- **Reminders have no recurrence and no source.** `user_reminders` holds `label`, `fire_at`, `sent`, `sent_at`, `created_at`. The route returns those and no invented fields.
- **The reminder–loop link is already on loops.** `LoopListItem.reminder_id` exists (173). The client joins reminders to loops; the plugin does not look up loops, and no `ze_sdk` loop lookup is added.
- **Hypothesis feedback is stored but never written or read today.** The new feedback route writes it (or clears it with `null`, which is the undo), and the push sweep, `PriorityView` and the conversational lookup (`who_is_on_project`) stop offering `not_relevant` and `muted` hypotheses, so the button does what it says. `SocialCooccurrenceJob` keeps seeing them (it updates their evidence). Feedback on a confirmed hypothesis is stored but changes nothing: a confirmed hypothesis lists as confirmed.
- **A promoting corroboration writes confidence once.** Today it calls `set_confidence` and then `promote`; with the new stamp the prior would be the intermediate value. The promote path calls `promote` alone (0.7 is above the 0.6 corroboration cap, so `GREATEST` always takes it) and falls back to `set_confidence` only when `promote` returns none.

## Overview

Four values the new places need are not available over REST:

1. **Interruption budget and what happened to each push (gap 3).** The governor (177) counts discretionary pushes against `proactive.budget.max_pushes_per_day` in a rolling 24-hour window, but no endpoint says how many are used, when the next slot opens, or what proactive jobs ran. Governance › Attention budget and World › "While you were away" need them.
2. **Loop confidence movement (gap 4).** Loop rows carry `confidence` but not the value before its last change. The confidence sparkline (DESIGN.md Rows) needs both ends.
3. **Hypotheses as a list (gap 6).** Correlation hypotheses are only visible inside the priority snapshot. Mind's entity view and the "I suspect …" sentence need a list with confidence, relation, evidence and entities, and a way to dismiss one.
4. **Reminders as first-class REST (gap 12).** Reminders exist only as the Reminders plugin's server-driven page. World places them on the field as deadlines on concerns, linked through `open_loops.reminder_id`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The budget is visible (Priority: P1)

`GET /api/v0/notifications/budget` (`getAttentionBudget`) returns `{ used, max_per_day, remaining, window_hours, next_slot_at, held_count, quiet_hours_active }`. `used` and `next_slot_at` come from `ze_proactive.attention_budget.budget_status()`, the same function the notifier's claim path uses (one count). `next_slot_at` is the time enough counted claims leave the window for one slot to open: the `(used - max_per_day + 1)`-th oldest claim + 24 h, set only when `remaining == 0` (so it stays right when `used` exceeds the maximum, after the maximum is lowered or two claimers race). `held_count` and the budget maximum move here from `getQuietHours` (hard cut).

**Independent Test**: with a fake push log holding three attention claims in the last 24 hours (oldest 20 hours ago) and `max_per_day: 3`, the route returns `used: 3`, `remaining: 0`, `next_slot_at` = oldest + 24 h. With two claims, `next_slot_at` is null. With four claims and `max_per_day: 3`, it is the second-oldest + 24 h.

### User Story 2 - What Ze sent and ran is listable (Priority: P2)

`GET /api/v0/notifications` gains filters `delivery` (repeatable: `delivered | held | released | suppressed | failed`), `push_class` (`requested | accountability | discretionary`) and `since` (matches `COALESCE(delivered_at, created_at) > since`, so a held push released after the user left is listed), and items gain `urgency` and `delivered_at`. `GET /api/v0/proactive/job-runs?since=` (`listProactiveJobRuns`) lists the last run of each proactive job: `job_id`, `last_started_at`, `last_finished_at`, `last_status` (`running | ok | error`).

**Independent Test**: route tests over fake stores; `delivery=held&delivery=suppressed` passes both values to the store; a row created before `since` and released after it is listed; job-run status is a closed enum; a job-run store failure is a 503, not an empty list.

### User Story 3 - A loop's sparkline has a real start (Priority: P1)

Loop rows gain `confidence_prior` (the value before the last confidence change) and `confidence_changed_at`. Every store write that changes `confidence` stamps both in the same UPDATE, and only when the value actually changes (migration `zw005`, columns nullable). Loop REST rows also gain `drift_deadline` and `confirmed_at`, which World places on the field. Loop `ClaimPosture.confidence_from` is filled from `confidence_prior` (after 184).

**Independent Test**: real-Postgres tests: corroboration from 0.4 writes prior 0.4 and the new value; a write with an unchanged value leaves prior and timestamp alone; a loop never changed returns nulls.

### User Story 4 - Hypotheses are a list the user can dismiss (Priority: P1)

`GET /api/v0/hypotheses?entity_id=&state=open|confirmed|dismissed|all&limit=` (`listHypotheses`) returns hypotheses newest first with `id`, `summary`, `narrative`, `relation`, `confidence`, `claim_kind` (`inference` | `suspicion` only), `evidence` (`kind`, `id`, `label`), `entities` (`id`, `name` or null), `surfaced`, `feedback`, `confirmed`, `created_at`. `POST /api/v0/hypotheses/{id}/feedback` (`setHypothesisFeedback`) records `useful | not_relevant | muted`, or `null` to clear it; `not_relevant` and `muted` hypotheses are no longer pushed, ranked or offered by `who_is_on_project`. Owned by `ze-correlation` (`ze_correlation/rest.py`), routed by ze-api.

**Independent Test**: store fake with two hypotheses on an entity and one elsewhere; the entity filter returns two; `claim_kind` never `fact`; after `muted` feedback, `list_unsurfaced`, `list_recent` and `list_by_entities` (default) skip the hypothesis; clearing it brings it back.

### User Story 5 - Reminders have REST (Priority: P1)

`GET /api/v0/reminders?status=upcoming|overdue|fired|all&limit=` (`listReminders`) returns `{ id, label, fire_at, sent_at, status }` with `status` one of `upcoming` (not sent, `fire_at` in the future), `overdue` (not sent, `fire_at` passed: missed while Ze was down, replay not yet run) or `fired` (sent); the filter accepts `upcoming | overdue | fired | all`; ISO timestamps with offset. Owned by `ze-calendar` (plugin `rest_routes()`). The client joins a reminder to its loop through `LoopListItem.reminder_id`. The plugin page (`getRemindersPage`) is deleted in phase 186 when World renders reminders, not here.

**Independent Test**: plugin route test with a fake reminder store: `upcoming` returns unsent future reminders ordered by `fire_at`; an unsent reminder whose time passed is `overdue`, never `upcoming`; `fired` returns sent ones newest first.

### Edge Cases

- Budget store failure, or a notifier built without a push log: the route returns 503 with a typed error. The notifier keeps its fail-open behaviour (it sends when the count fails); the route never shows a guessed number.
- `confidence_prior` is never back-computed for old rows (pre-v1: nulls are honest).
- A promotion that does not raise confidence (`GREATEST` keeps the old value) does not stamp a change.
- A hypothesis promoted to identity still lists, with `confirmed: true`.
- An entity id no longer in memory lists with `name: null`.
- Reminder plugin disabled: `/api/v0/reminders` is absent (404), and World omits reminders.

## Requirements *(mandatory)*

- **FR-001**: `ze_proactive.attention_budget.budget_status(push_log, max_per_day, *, window_hours=24.0) -> BudgetStatus`; `within_budget` and `ProactiveNotifier.remaining_budget` call it; `ProactiveNotifier.budget_status()` wraps it for the route; `PushLogStore.count_sent_within_hours` is replaced by `window_sent_at(event_type, hours) -> list[datetime]` (ascending; hard cut).
- **FR-002**: `getAttentionBudget`; `QuietHoursResponse` loses `held_count` and `max_discretionary_per_day` (hard cut; Settings reads the budget query).
- **FR-003**: `listNotifications` filters (`delivery`, `push_class`, `since` on `COALESCE(delivered_at, created_at)`) and fields (`urgency`, `delivered_at`); `listProactiveJobRuns` over a non-swallowing `JobRunStore.list_runs()`.
- **FR-004**: `zw005` adds `open_loops.confidence_prior REAL NULL`, `open_loops.confidence_changed_at TIMESTAMPTZ NULL`; `PostgresLoopStore.set_confidence`, `stamp_declared` and `promote` stamp them when the value changes; the promote path of `corroboration.py` writes confidence once; `OpenLoop`, `LoopListItem` (+ `drift_deadline`, `confirmed_at`) and `LoopSignal` carry them; the 184 loop postures fill `confidence_from`.
- **FR-005**: `listHypotheses` and `setHypothesisFeedback` in `ze-correlation`, routed by ze-api; `claim_kind` is `inference` | `suspicion` only; feedback filters the push sweep, `PriorityView` and `list_by_entities` (opt-out `include_dismissed=True` for `SocialCooccurrenceJob`); `HypothesisNotFoundError` becomes a `ZeError`.
- **FR-006**: `listReminders` in `ze-calendar` via `rest_routes()`; no `ze_worldstate` import, no new `ze_sdk` surface.
- **FR-007**: Every new or changed route declares `response_model`, `summary`, `description`, `operation_id`; `make codegen`; web changes limited to what the hard cuts require (Settings quiet-hours form and the `/jarvis` reference model read `getAttentionBudget`).

## Success Criteria *(mandatory)*

- **SC-001**: Every new route has OpenAPI `response_model`, `summary`, `description`, `operation_id`, and a route test.
- **SC-002**: `rtk proxy grep -rn "count_sent_within_hours\|window_sent_at" core apps` shows one window query, called only from `budget_status`.
- **SC-003**: `make test-py`, `make test-pg` (zw005), `make lint`, `make typecheck-web`, `make test-web` pass; `packages/ze-sdk/tests/test_plugin_boundaries.py` passes.

## Out of Scope

- Any new web page (186, 189, 190 consume these).
- A calendar-day budget, a job-run history table, reminder recurrence.
- Calendar event reminders (`calendar_reminders`).
- Action ledger, collisions, tier default, screen-context echo (194, B4); voice (192, B3).

## Owning packages and migrations

ze-proactive (budget function, push-log window query, notification filters), ze-api (routes), ze-worldstate (`zw005`, store writes, REST row), ze-priority (`LoopSignal`, 184 postures), ze-correlation (hypotheses REST, feedback), ze-personal (`who_is_on_project` and `SocialCooccurrenceJob` callers of `list_by_entities`), ze-calendar (reminders REST), ze-web (hard-cut follow-up only). No `ze_sdk` change.
