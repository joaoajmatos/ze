# Implementation Plan: World Data Gaps (B2)

**Branch**: `185-world-data-gaps` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications 2026-10-17 are binding), code on `main` at fd79e51d, 184 floor at 9ca300d8 (line references to `compose/rules.py::_loop_posture`, `_loop_card_from_item`, `test_rules_slipping.py:116` and `test_composer.py:82` are from that commit; T001 re-checks). Revised after Gauge's review (W-1..W-12).

## Summary

Five read surfaces and one write, each a thin route over a store that already holds the data, plus one migration. The budget route reuses the governor's own count. The push-outcome view extends `listNotifications`, because outcomes live on `notifications.delivery`, not on `push_log`. Loop confidence movement is stamped inside the three store methods that write `confidence`; only the promote path of corroboration changes, so it writes once. Hypotheses get a list and a feedback write, and the feedback now filters what is pushed and ranked. Reminders get a plugin route; the client joins them to loops through the existing `LoopListItem.reminder_id`.

## Technical Context

**Language/Version**: Python 3.12 (FastAPI, asyncpg), TypeScript 5 (ze-web, generated client).
**Primary Dependencies**: no new ones. No new package edges: ze-api already depends on ze-proactive, ze-worldstate, ze-correlation, ze-memory; ze-correlation already depends on ze-memory; ze-calendar keeps `ze_sdk` only.
**Storage**: Postgres. One migration `zw005` (ze-worldstate chain, after `zw004`). No ze-proactive, ze-correlation or ze-calendar migration.
**Testing**: pytest (`asyncio_mode = auto`), fakes and `AsyncMock` pools; `@pytest.mark.pg` for the confidence stamps; vitest for the two web consumers.
**Constraints**: pre-v1 hard cuts (no aliases for `count_sent_within_hours`, `QuietHoursResponse.held_count`, `max_discretionary_per_day`); plugin boundary (`test_plugin_boundaries.py`); no System One judge text changes; no live calls.
**Scale**: single user; every list is bounded (`limit` ≤ 200, job runs bounded by registered jobs).

## Constitution Check

| Principle | Check |
|---|---|
| Spec first | spec.md with Clarifications; plan and tasks here. |
| Honest claims | Every value comes from a stored record. The budget states its real rule (rolling 24 h). `confidence_prior` is null until a change is stamped; never back-filled. Entity names are null when memory no longer has them. |
| Package boundaries | ze-calendar imports only `ze_sdk`; it does not resolve loops. ze-correlation REST lives in the package; ze-api routes it. |
| Pre-v1 hard cuts | `count_sent_within_hours` replaced; quiet-hours budget fields moved, consumers updated in the same change. |
| Tests | Fail-first per task; pg test for the migration's write behaviour. |
| Docs are part of done | [DOCS] tasks cover every doc in "Docs touched". |

## Blast radius

From `graphify affected <symbol> --depth 2` (graph updated on the floor at plan time) and `rtk proxy grep`:

| Symbol | Callers (by package) | Change |
|---|---|---|
| `within_budget` (ze-proactive) | `try_claim_shared`, `ProactiveNotifier.notify`; tests `test_attention_budget.py` (8), `apps/ze-api/tests/test_governor_acceptance.py`, `test_workspace_followthrough.py`; importers in ze-api `wiring/{agents,container,jobs}.py`, ze-automation goals (import the module, not this name) | Body calls `budget_status`; signature unchanged. |
| `PushLogStore.count_sent_within_hours` | `attention_budget.within_budget`, `ProactiveNotifier.remaining_budget` (only two; grep) | Replaced by `window_sent_at`; fakes in `test_attention_budget.py` and the notifier tests rename the method. |
| `ProactiveNotifier.remaining_budget` | grep at T001 (used by the goal/workflow planners' budget text) | Calls `budget_status`; new `ProactiveNotifier.budget_status()` for the route. |
| `QuietHoursResponse`, `_quiet_hours_response` | `notifications/router.py` (`get_quiet_hours`, `update_quiet_hours`), `v0/__init__.py` re-export, tests `test_notifications_route.py`, `test_quiet_hours_routes.py`; web `QuietHoursSettings.tsx` (+ test), `pages/jarvis/model/world.ts` | Two fields removed; web reads `getAttentionBudget`. |
| `NotificationStore.list_page`, `Notification` | `notifications/router.py`; tests; 184 adds `target_parent_id` beside them | New keyword filters; `Notification` gains `delivered_at`. |
| `JobRunStore` | ze-api `wiring/stores.py` (`CoreStores.job_run_store`), `ProactiveScheduler` (uses `get_all`, which swallows errors on purpose); tests `test_job_run_store.py` | New `list_runs()` that raises; new deps getter. |
| `PostgresLoopStore` (`set_confidence`, `stamp_declared`, `promote`, `_loop_from_row`) | callers of the three writes: `decay.cascade_from_evidence`, `corroboration` (set + promote; the promote path changes to one write), `tracking.LoopTracker` (set + stamp), `review.confirm` (stamp); pg tests in `apps/ze-api/tests/pg/` (`test_acceptance`, `test_drift`, `test_loop_confirmation_pg`, `test_loop_evidence`); unit tests `core/cognition/ze-worldstate/tests/{test_store,test_tracking,test_corroboration_flow,test_graph_integration}.py` | SQL changes inside the store; caller signatures unchanged; `corroboration.py` promote path calls `promote` alone. |
| `OpenLoop` (types) | every worldstate module, ze-priority `scoring.py`, 184 `compose/rules.py` | Two optional fields with defaults; no caller breaks. |
| `_loop_to_list_item`, `LoopListItem` | `ze_worldstate.rest.list_loops`, `tests/test_rest.py` (6), ze-api `loops/router.py`; web `entities/loop` | Four fields added. |
| `LoopSignal` (ze-priority) | `scoring.py:54` (only constructor); 184 `compose/rules.py::_loop_card_from_item` | `confidence_prior` field. |
| `PostgresHypothesisStore` | `build_correlation_stack`, `CorrelationEngine`, `HypothesisDecayJob`, `HypothesisPushSweep` (`push.py`), `PriorityView` (`view.py`); tests `ze-correlation/tests/test_store.py`, `test_engine.py` | New `list_for_display`, `set_feedback`; `list_unsurfaced`, `list_recent` and `list_by_entities` gain a feedback predicate; `HypothesisNotFoundError` becomes a `ZeError`. |
| `PostgresHypothesisStore.list_by_entities` | ze-personal `social/tools.py:63` (`who_is_on_project`: hides dismissed by default), `jobs/social_cooccurrence.py:161` (passes `include_dismissed=True`: it updates their evidence) | New keyword `include_dismissed: bool = False`. |
| `ReminderStore` | ze-calendar agent and tools, `fire_reminder`, `plugin.py`; tests in `plugins/ze-calendar/tests/` | New `list_by_status`; nothing else changes. |

Out-of-graph surfaces checked by grep: `max_discretionary_per_day` (two web files and one test), `held_count` (same), `getRemindersPage` (unchanged here). Docs naming these surfaces: see "Docs touched".

## Design

### ze-proactive: one budget count

```python
@dataclass(frozen=True)
class BudgetStatus:
    max_per_day: int
    window_hours: float
    counted_at: tuple[datetime, ...]   # sent_at of every counted claim, ascending

    @property
    def used(self) -> int: return len(self.counted_at)
    @property
    def remaining(self) -> int: return max(0, self.max_per_day - self.used)
    @property
    def next_slot_at(self) -> datetime | None:
        # One slot opens when used - max + 1 claims have left the window.
        if self.remaining > 0 or self.max_per_day == 0: return None  # max 0: discretionary pushes are off; no slot opens
        return self.counted_at[self.used - self.max_per_day] + timedelta(hours=self.window_hours)

async def budget_status(push_log, max_per_day, *, window_hours=24.0) -> BudgetStatus  # raises on store failure
async def within_budget(push_log, max_per_day, *, window_hours=24.0) -> bool          # budget_status(...).remaining > 0; fail-open as today
```

`PushLogStore.window_sent_at(event_type, hours) -> list[datetime]` runs `SELECT sent_at FROM push_log WHERE event_type = $1 AND sent_at > NOW() - ($2 * INTERVAL '1 hour') ORDER BY sent_at ASC` (the window holds a handful of claims; no cap needed). `count_sent_within_hours` is deleted. `ProactiveNotifier.budget_status()` raises `BudgetUnavailableError` (new `ZeError` subclass in `ze_proactive/errors.py`) when the notifier has no push log, and lets a store failure raise; `remaining_budget()` calls it and falls back to `max` on any failure as today. `BudgetStatus` lives in `ze_proactive/types.py`.

`NotificationStore.list_page` gains `delivery: Sequence[str] | None`, `push_class: str | None`, `since: datetime | None` (each an AND condition, parameterized; values validated against the zpro004 enums at the route). `since` matches `COALESCE(delivered_at, created_at) > $n`: a held push released after the user left counts as news. Ordering and cursor stay on `created_at`. `Notification` gains `delivered_at: datetime | None` (`urgency` is already there).

### ze-api: routes

- `api/v0/notifications/router.py`: `GET /notifications/budget` → `AttentionBudgetResponse { used, max_per_day, remaining, window_hours, next_slot_at, held_count, quiet_hours_active }`, from `notifier.budget_status()` (the existing `get_notifier` dependency; ze-api never reads the push log directly). `BudgetUnavailableError` or a store failure → 503. `QuietHoursResponse` drops `held_count`, `max_discretionary_per_day`. `listNotifications` gains `delivery: list[DeliveryLiteral] | None = Query(None)`, `push_class: PushClassLiteral | None`, `since: datetime | None`; `NotificationItem` gains `urgency`, `delivered_at`. Route order: `/budget` declared before any `/{id}` path.
- `api/v0/proactive/{router,schemas}.py` (new): `GET /proactive/job-runs?since=` → `list[ProactiveJobRunItem]`, sorted by `last_started_at` desc, filtered `last_started_at >= since`. It calls a new `JobRunStore.list_runs()` that lets errors raise (→ 503); `get_all` keeps swallowing for the scheduler. `deps.get_job_run_store` reads the container's `job_run_store` (T001 confirms the attribute path from `CoreStores`).
- `api/v0/hypotheses/{router,schemas}.py` (new): `GET /hypotheses` and `POST /hypotheses/{id}/feedback`, calling `ze_correlation.rest`. `deps.get_hypothesis_store` and an entity-name lookup from the memory store (`get_entities_by_ids`; T001 names the container attribute). Unknown id → 404 (`HypothesisNotFoundError`, now a `ZeError` subclass, mapped in ze-api `errors.py`). Every new router has `dependencies=[Depends(require_api_key)]`.
- Register both routers in `api/v0/__init__.py` like `loops`.

### ze-worldstate: confidence movement

`zw005_loop_confidence_prior.py`: `ALTER TABLE open_loops ADD COLUMN IF NOT EXISTS confidence_prior REAL NULL, ADD COLUMN IF NOT EXISTS confidence_changed_at TIMESTAMPTZ NULL`; downgrade drops both.

One SQL fragment in `store.py`, used by the three writers (Postgres evaluates every SET expression against the old row):

```sql
confidence_prior      = CASE WHEN confidence IS DISTINCT FROM {new} THEN confidence ELSE confidence_prior END,
confidence_changed_at = CASE WHEN confidence IS DISTINCT FROM {new} THEN now() ELSE confidence_changed_at END,
confidence            = {new}
```

`{new}` is `$2` in `set_confidence` and `stamp_declared`, and `GREATEST(confidence, $2)` in `promote`. `create` leaves both null. `OpenLoop` gains `confidence_prior: float | None = None`, `confidence_changed_at: datetime | None = None`; `_loop_from_row` reads them. `rest._loop_to_list_item` adds `confidence_prior`, `confidence_changed_at`, `drift_deadline`, `confirmed_at` (ISO or null); `LoopListItem` mirrors them. The decay, tracking and review modules do not change.

`corroboration.py` (lines 181–193 on `main`) makes two writes when it promotes: `set_confidence(corroborated)` and then `promote(0.7, GREATEST)`. With the stamp, the prior would read the intermediate value. Change: for `decision.kind == "corroborate"` call `set_confidence` as today; for `"promote"` call `promote` alone (0.7 is above `CORROBORATED_CAP` 0.6, so `GREATEST` always takes 0.7 or keeps a higher value) and call `set_confidence(corroborated)` only when `promote` returns `None` (the loop left `suspected` meanwhile). The outcome strings stay the same.

### ze-priority: loop postures (after 184)

`LoopSignal.confidence_prior: float | None = None`; `scoring.py` fills it from the loop. 184's `compose/rules.py::_loop_posture` sets `confidence_from=loop.confidence_prior`, and `_loop_card_from_item` sets `confidence_from=signal.confidence_prior`. `TurnSurfacing.mention_cards` builds its loop cards through the same helpers (T001 confirms on `main`); hypothesis postures keep `confidence_from=None`.

### ze-correlation: list and feedback

`store.py`:
- `list_for_display(*, entity_id: UUID | None, state: Literal["open","confirmed","dismissed","all"], limit: int) -> list[Hypothesis]`: `open` = `NOT confirmed AND (feedback IS NULL OR feedback = 'useful')`; `confirmed` = `confirmed`; `dismissed` = `feedback IN ('not_relevant','muted')`; entity filter `entities ? $n` (the jsonb array of id strings, as `list_by_entities` uses); `ORDER BY created_at DESC LIMIT`.
- `set_feedback(hypothesis_id, feedback: Literal[...] | None) -> Hypothesis` (`RETURNING *`; none → `HypothesisNotFoundError`). `None` clears feedback (the undo for a dismissal). Feedback on a confirmed hypothesis is stored and changes nothing else; `confirmed` wins in `list_for_display` (`dismissed` = `NOT confirmed AND feedback IN (...)`).
- `list_unsurfaced`, `list_recent` and `list_by_entities(entity_ids, *, include_dismissed=False)` add `AND (feedback IS NULL OR feedback = 'useful')` (the last one unless `include_dismissed`). `SocialCooccurrenceJob` passes `include_dismissed=True`; `who_is_on_project` keeps the default.
- `HypothesisNotFoundError` subclasses `ZeError` (from `ze_agents.errors`).

`rest.py` (new): `list_hypotheses(store, entity_names, *, entity_id, state, limit) -> list[dict]` and `set_feedback(store, id, feedback) -> dict`. `entity_names: Callable[[list[UUID]], Awaitable[dict[UUID, str]]]` is passed in by ze-api so the package keeps no wiring knowledge; one call per page with the union of entity ids. `claim_kind` is asserted in `{inference, suspicion}`; a row with another value is skipped and logged (`hypothesis_claim_kind_invalid`), never returned.

### ze-calendar: reminders route

`ReminderStore.list_by_status(status: Literal["upcoming","overdue","fired","all"], limit: int) -> list[Reminder]`: upcoming = `NOT sent AND fire_at > NOW() ORDER BY fire_at ASC` (as `list_pending`); overdue = `NOT sent AND fire_at <= NOW() ORDER BY fire_at ASC`; fired = `sent ORDER BY sent_at DESC NULLS LAST`; all = `ORDER BY fire_at DESC`. The route derives `status` per row with the same rule (now from the database clock in the query: select `fire_at <= NOW() AS due`). `api/routes.py` adds `GET /api/v0/reminders` (`listReminders`) → `list[ReminderItem { id, label, fire_at, sent_at, status }]`, store from `request.app.state.container._plugin_stores["reminder_store"]` as `get_reminders_page` does; store missing → empty list; `limit` defaults to 50 and is clamped 1..200.

### Web (hard-cut follow-up only)

Generated client: `packages/ze-client/src/generated/*` belongs to the ENG lane. Every task that changes the OpenAPI ends with `make codegen`, and ENG commits the regenerated files with it (for a JR route task, ENG regenerates and commits right after merging it). JR tasks never edit `generated/*`. `entities/notification/api/useAttentionBudgetQuery.ts` (exported from the entity index). `widgets/settings-workspace/ui/QuietHoursSettings.tsx` reads `max_per_day` and `held_count` from it; `pages/jarvis/model/world.ts` likewise. No other screen changes; 186/189/190 add their own hooks.

## Project Structure

### Documentation (this feature)

```
specs/phases/185-world-data-gaps/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code

```
core/contracts/ze-proactive/ze_proactive/{attention_budget,push_log_store,notifier,notification_store,types}.py
core/cognition/ze-worldstate/ze_worldstate/{store,types,rest}.py
core/cognition/ze-worldstate/ze_worldstate/migrations/versions/zw005_loop_confidence_prior.py
core/arbitration/ze-priority/ze_priority/{types,scoring}.py, compose/rules.py (184)
core/cognition/ze-correlation/ze_correlation/{store,rest}.py
plugins/ze-calendar/ze_calendar/{reminders/store.py,api/routes.py,api/schemas.py}
apps/ze-api/ze_api/api/{deps.py,v0/__init__.py,v0/notifications/*,v0/loops/schemas.py,v0/proactive/*,v0/hypotheses/*}, ze_api/errors.py
apps/ze-web/src/entities/notification/api/useAttentionBudgetQuery.ts, widgets/settings-workspace/ui/QuietHoursSettings.tsx, pages/jarvis/model/world.ts
packages/ze-client/src/generated/*
```

## Docs touched ([DOCS] tasks)

- `docs/native-interface.md`: budget route, notification filters, job-runs route, quiet-hours response change.
- `docs/architecture.md`: REST tables (line ~854 already lists `GET /api/v0/reminders listReminders`, which this phase makes true; add budget, job-runs, hypotheses rows) and the `push_log` row (~973: claims, not outcomes).
- `docs/frontend.md` (~121): quiet-hours widget and hooks (live path `widgets/settings-workspace/ui/QuietHoursSettings.tsx`; fix stale names).
- `docs/package-architecture.md` (~106): `PushLogStore` description.
- `core/arbitration/ze-priority/README.md` (~49): `max_pushes_per_day` is a rolling 24-hour budget.
- `docs/scheduled-jobs.md`: job-runs route; budget is a rolling 24-hour window with `next_slot_at`.
- `docs/configuration.md`: `proactive.budget.max_pushes_per_day` text says "rolling 24 hours" if it says "per day" only.
- `docs/cognitive-architecture.md` and `docs/memory.md` (only if they describe loop confidence): confidence moves on evidence, prior value kept.
- `docs/features.md`: hypotheses list and dismiss; reminders REST.
- `core/contracts/ze-proactive/README.md`, `core/cognition/ze-worldstate/README.md` (zw005), `core/cognition/ze-correlation/README.md` (REST), `plugins/ze-calendar/README.md` (route) if present.
- `AGENTS.md`: phase 185 row; migration table `zw005`; ze-worldstate layout line adds `zw005`.
- `specs/README.md` row 185 → Implemented; `specs/phases/184-composed-answers-posture/contracts/claim-descriptors.md` `confidence_from` line: "the value before the last change (loops, phase 185)".

## Complexity Tracking

None. No new package, edge, table, or judge.
