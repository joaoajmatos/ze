# Feature Specification: World Data Gaps (B2)

**Feature Branch**: `185-world-data-gaps`

**Created**: 2026-10-17

**Status**: Draft (spec level; plan and tasks follow once scheduled)

**Input**: Maestro brief 2026-10-17, backend floor B2: overhaul plan section d, gaps 3, 4, 6, 12.

**Governed by**: `specs/arch/claim-topology.md`, `specs/arch/pre-v1-hard-cuts.md`, `DESIGN.md` ("a value the API does not expose is omitted, not faked"). Prior phases: 57 (correlation hypotheses), 109–111 (loops, claim decay), 172 (corroboration), 173 (`open_loops.reminder_id`), 177 (interruption governor, `push_log`, `proactive_job_runs`), 13/22 (reminders).

**Depends on**: 184 (B1) for `ClaimPosture.confidence_from`, which this phase fills for loops. Should land before 186 (World), 189 (Mind) and 190 (Governance); each of those degrades gracefully (omits the value) without it.

**Doctrine functions served**: executive function (reminders as deadlines on concerns, honest decay), reflection (hypotheses as claims the user can inspect), governance (the interruption budget is visible).

---

## Overview

Four values the new places need are not available over REST:

1. **Interruption budget today and the push log (gap 3).** The governor (177) counts discretionary pushes against `proactive.budget.max_pushes_per_day`, but no endpoint says how many are used today, which were held by quiet hours, or what proactive jobs ran. Governance › Attention budget and World › "While you were away" need them.
2. **Loop decay "from" value (gap 4).** Loop rows carry `confidence` (decayed) but not the value at the last evidence. The confidence sparkline (DESIGN.md Rows) needs both ends.
3. **Hypotheses as a list (gap 6).** Correlation hypotheses are only visible inside the priority snapshot. Mind's entity view and the "I suspect …" sentence need a list with confidence, relation, evidence and entities.
4. **Reminders as first-class REST (gap 12).** Reminders exist only as the Reminders plugin's server-driven page. World places them on the field as deadlines on concerns, linked through `open_loops.reminder_id`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The budget is visible (Priority: P1)

`GET /api/v0/notifications/budget` returns `{ used_today, max_per_day, held_count, quiet_hours_active, resets_at }` computed by the governor's own counting function (one source of truth with `decide()`), in the user's timezone day.

**Independent Test**: with a fake push log holding three discretionary pushes today, one yesterday and one accountability push today, the route returns `used_today: 3` and `max_per_day` from config.

### User Story 2 - What Ze sent and ran is listable (Priority: P2)

`GET /api/v0/proactive/runs?since=` lists `proactive_job_runs` rows (job, started, finished, outcome) and `GET /api/v0/notifications/push-log?since=` lists `push_log` rows (event type, class, outcome: sent, held, deduped, over budget). Cursor-paginated like `listNotifications`.

**Independent Test**: route tests over fake stores; outcomes appear as closed enums, never free text.

### User Story 3 - A loop's sparkline has a real start (Priority: P1)

Loop REST rows and loop `ClaimPosture` gain `confidence_at_evidence` (the value stamped when evidence last changed it) and `evidence_at`. The decay cascade (`ze_worldstate/decay.py`) and corroboration write both in the same UPDATE that changes confidence (migration `zw005`, columns nullable; null → the client draws no sparkline).

**Independent Test**: corroboration and decay unit tests assert both columns are written with the confidence change; a loop never evidenced returns nulls.

### User Story 4 - Hypotheses are a list (Priority: P1)

`GET /api/v0/hypotheses?entity_id=&state=open|confirmed|all` returns hypotheses with `summary`, `relation`, `confidence`, `claim_kind` (inference or suspicion only), `evidence` (refs with kind and snippet), `entities`, `surfaced`, `feedback`, `confirmed`, `created_at`. Owned by `ze-correlation` (`ze_correlation/rest.py`), mounted by ze-api. Feedback actions reuse the existing correlation feedback path if one exists over REST; otherwise `POST /api/v0/hypotheses/{id}/feedback` (`useful` | `not_relevant` | `muted`).

**Independent Test**: store fake with two hypotheses on an entity and one elsewhere; the entity filter returns two; `claim_kind` never `fact`.

### User Story 5 - Reminders have REST (Priority: P1)

`GET /api/v0/reminders?status=upcoming|fired|all` returns reminders with `id`, `text`, `fire_at` (ISO with timezone), `recurrence` in words, `loop_id` (the loop whose `reminder_id` points at it), `source`. Owned by `ze-calendar` (plugin `rest_routes()`); the loop link is resolved through a `ze_sdk`-exposed loop lookup, not a `ze_worldstate` import. The plugin page descriptor (`getRemindersPage`) is deleted in phase 186 when World renders reminders, not here.

**Independent Test**: plugin route test with a fake reminder store and a fake loop lookup; a reminder linked from a loop carries its `loop_id`.

### Edge Cases

- Budget day boundary uses the user's configured timezone (`TimezoneService`), not UTC.
- `confidence_at_evidence` is never back-computed for old rows (pre-v1: nulls are honest).
- A hypothesis promoted to identity still lists, with `confirmed: true`.
- Reminder plugin disabled: `/api/v0/reminders` is absent (404), and World omits reminders.

## Requirements *(mandatory)*

- **FR-001**: Budget route in ze-api calls a new `ze_proactive.governor.budget_status(store, settings, now)` used by `decide()` too (refactor, no second count).
- **FR-002**: `push_log` and `proactive_job_runs` list routes with cursor pagination, `response_model`, `summary`, `description`, `operation_id` (`getPushBudget`, `listPushLog`, `listProactiveRuns`).
- **FR-003**: `zw005` adds `open_loops.confidence_at_evidence REAL NULL`, `open_loops.evidence_at TIMESTAMPTZ NULL`; every write path that changes `confidence` because of evidence sets both; loop REST and `TurnSurfacing.mention_cards` / `WorldComposer` cards fill `ClaimPosture.confidence_from` and `as_of` from them.
- **FR-004**: `listHypotheses` (+ feedback route if missing) in `ze-correlation`, mounted by ze-api; `claim_kind` is `inference` | `suspicion` only.
- **FR-005**: `listReminders` in `ze-calendar` via `rest_routes()`, with `loop_id` resolved through a lookup exposed in `ze_sdk` (no plugin import of `ze_worldstate`).
- **FR-006**: `make codegen`; no web screen changes in this phase beyond client regeneration.

## Success Criteria *(mandatory)*

- **SC-001**: Every new route has OpenAPI `response_model`, `summary`, `description`, `operation_id`, and a route test.
- **SC-002**: `rtk proxy grep` finds one budget counting function.
- **SC-003**: `make test-py`, `make test-pg` (zw005), `make lint` pass; `packages/ze-sdk/tests/test_plugin_boundaries.py` passes.

## Out of Scope

- Any web page (186, 189, 190 consume these).
- Action ledger, collisions, tier default, screen-context echo (194, B4); voice (192, B3).

## Owning packages and migrations

ze-proactive (budget function, push-log/run stores reads), ze-api (routes), ze-worldstate (`zw005`, decay/corroboration writes), ze-correlation (hypotheses REST), ze-calendar (reminders REST), ze-sdk (loop lookup re-export).
