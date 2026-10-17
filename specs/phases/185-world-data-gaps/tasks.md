# Tasks: World Data Gaps (B2)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md).

**Build gate**: start after 184 is on `main` (the floor branches from that `main`). The Spec Architect (Lintel) stays on call for design questions.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests use fakes and `AsyncMock` pools; no OpenRouter call; `@pytest.mark.pg` for real-Postgres checks (`make test-pg`).

**Lanes**: `[ENG]` Claude Sonnet lane lead (ze-proactive, ze-worldstate, ze-priority, ze-api wiring, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story.

**Tags**: `[BACKEND]` Python · `[WEB]` ze-web, generated clients · `[PLATFORM]` migration · `[DOCS]` docs and specs.

**Rules for the implementer**
- Before changing a signature in plan.md "Blast radius", run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "<symbol>" --include='*.py' core apps plugins packages eval`; update every caller in the same change.
- Every value comes from a stored record. No back-fill of `confidence_prior`; no guessed budget on store failure.
- Pre-v1 hard cut: delete `count_sent_within_hours`, `QuietHoursResponse.held_count`, `QuietHoursResponse.max_discretionary_per_day` in the change that replaces them; no aliases.
- ze-calendar imports only `ze_sdk` (boundary test).
- Generated client: `packages/ze-client/src/generated/*` belongs to ENG. Each task that changes the OpenAPI (T004, T007, T008, T011, T017, T020) is done only when `make codegen` has run and the regenerated files are committed with it; for a JR route task, ENG regenerates and commits right after merging it. JR never edits `generated/*`. Every intermediate commit passes the generated-client check.
- Every new router or route has `Depends(require_api_key)` and a 401 test.
- `get_logger(__name__)`; typed `ZeError` subclasses; no bare `Exception`/`ValueError` raised in domain code.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [x] T001 [ENG] [BACKEND] Branch from `main` with 184 merged. `graphify update .`, then `graphify affected` on `within_budget`, `PushLogStore`, `ProactiveNotifier`, `NotificationStore`, `QuietHoursResponse`, `JobRunStore`, `PostgresLoopStore`, `OpenLoop`, `LoopSignal`, `PostgresHypothesisStore`, `ReminderStore`, `_loop_to_list_item`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) the `zw` chain head (expect `zw004`); (c) every caller of `remaining_budget`; (d) the container attribute paths for `job_run_store`, the hypothesis store and the memory store's `get_entities_by_ids`; (e) the 184 line references in plan.md (taken from 9ca300d8) still match `main`; (f) whether `TurnSurfacing.mention_cards` builds loop postures through `compose/rules.py` helpers or its own constructor; (g) `corroboration.py` promote path still matches plan.md (set then promote). Stop and report differences to the Spec Architect.

## Phase 1: Budget [US1]

- [x] T002 [ENG] [BACKEND] Tests first in `core/contracts/ze-proactive/tests/test_attention_budget.py` (rename fakes' `count_sent_within_hours` to `window_sent_at` returning an ascending list): `budget_status` returns used/remaining; `next_slot_at` = oldest + 24 h when `used == max`; with `used = max + 1` it is the second-oldest + 24 h; null when `remaining > 0` or `max == 0`; `budget_status` raises on store failure; `within_budget` stays fail-open; `try_claim_shared` behaviour unchanged. In `test_notifier.py`: `ProactiveNotifier.budget_status()` raises `BudgetUnavailableError` with no push log and propagates a store failure; `remaining_budget` still falls back to max. Add `BudgetStatus` (`types.py`), `budget_status`, `BudgetUnavailableError` (`errors.py`), `PushLogStore.window_sent_at`, `ProactiveNotifier.budget_status`; delete `count_sent_within_hours`. Update notifier test fakes.
- [x] T003 [ENG] [BACKEND] `apps/ze-api/tests/pg/test_push_log_window_pg.py` (`@pytest.mark.pg`): three claims inside the window and one outside → `window_sent_at` returns the three, ascending.
- [x] T004 [ENG] [BACKEND] Tests first in `apps/ze-api/tests/api/test_notifications_route.py` and `test_quiet_hours_routes.py`: `GET /api/v0/notifications/budget` returns the seven fields from fakes (the US1 independent test); the route calls `notifier.budget_status()` (fake notifier via `get_notifier`); `BudgetUnavailableError` and a store failure → 503 (never `used: 0`); no API key → 401; `getQuietHours` no longer has `held_count` or `max_discretionary_per_day`. Implement `AttentionBudgetResponse`, the 503 mapping, the route (`getAttentionBudget`, summary, description), and the `QuietHoursResponse` cut. `make codegen`; commit the generated files with this task.
- [x] T005 [JR] [WEB] After T004's commit (which carries the regenerated client): `apps/ze-web/src/entities/notification/api/useAttentionBudgetQuery.ts` (exported from `entities/notification/index.ts`); `widgets/settings-workspace/ui/QuietHoursSettings.tsx` and its test read `max_per_day` and `held_count` from it; `pages/jarvis/model/world.ts` likewise. `make typecheck-web`, `make test-web`.

## Phase 2: Push outcomes and job runs [US2]

- [x] T006 [ENG] [BACKEND] Tests first in `core/contracts/ze-proactive/tests/test_notification_store.py`: `list_page(delivery=["held","suppressed"], push_class="discretionary", since=t)` builds one parameterized WHERE with all three conditions and the cursor; `since` compares `COALESCE(delivered_at, created_at)`; no filters → today's SQL. Add a `@pytest.mark.pg` case in `apps/ze-api/tests/pg/test_notification_filters_pg.py`: a held row created before `since` and released after it is returned; a row delivered before `since` is not. `Notification` gains `delivered_at`. Implement.
- [x] T007 [JR] [BACKEND] Tests first in `apps/ze-api/tests/api/test_notifications_route.py`: `delivery=held&delivery=suppressed` reaches the store as a list; an unknown delivery value → 422; items carry `urgency` and `delivered_at`. (ENG regenerates the client after merge.) Implement the `listNotifications` query params (Literal types for the zpro004 enums) and `NotificationItem` fields in `apps/ze-api/ze_api/api/v0/notifications/{router,schemas}.py`.
- [x] T008 [JR] [BACKEND] Tests first in `core/contracts/ze-proactive/tests/test_job_run_store.py`: `list_runs()` maps rows and raises on a pool error (unlike `get_all`). Tests first `apps/ze-api/tests/api/test_proactive_job_runs_route.py` (fake `JobRunStore.list_runs`): sorted by `last_started_at` desc; `since` filters; status enum; store failure → 503; no API key → 401. Implement `JobRunStore.list_runs`, `apps/ze-api/ze_api/api/v0/proactive/{__init__,router,schemas}.py` (`listProactiveJobRuns`), `deps.get_job_run_store` (path from T001), register in `api/v0/__init__.py`. (ENG regenerates the client after merge.)

## Phase 3: Loop confidence movement [US3]

- [ ] T009 [ENG] [PLATFORM] `core/cognition/ze-worldstate/ze_worldstate/migrations/versions/zw005_loop_confidence_prior.py` (revision `zw005`, down `zw004`; upgrade adds both nullable columns, downgrade drops them). Extend the migration-chain test if one lists `zw` heads (grep `zw004` in `apps/ze-api/tests`).
- [ ] T010 [ENG] [BACKEND] Tests first `apps/ze-api/tests/pg/test_loop_confidence_prior_pg.py` (`@pytest.mark.pg`, `_builders.make_loop`): `set_confidence` from 0.4 to 0.55 stamps prior 0.4 and a timestamp; the same value again leaves both unchanged; `stamp_declared` stamps; `promote` with a lower confidence argument (GREATEST keeps the old value) stamps nothing; a loop at 0.62 rewritten with 0.62 (Python float vs `REAL`) stamps nothing; a fresh loop has nulls; `get` and `list` return the fields. Implement the shared SQL fragment in `PostgresLoopStore.set_confidence`, `stamp_declared`, `promote`; `OpenLoop` fields; `_loop_from_row`.
- [ ] T011 [ENG] [BACKEND] Tests first in `core/cognition/ze-worldstate/tests/test_rest.py`: list items carry `confidence_prior`, `confidence_changed_at`, `drift_deadline`, `confirmed_at` (ISO or null). Implement `_loop_to_list_item` and `apps/ze-api/ze_api/api/v0/loops/schemas.py::LoopListItem`. `make codegen`; commit the generated files with this task.
- [ ] T012 [ENG] [BACKEND] Tests first in `core/cognition/ze-worldstate/tests/test_corroboration_flow.py`: a promote decision calls `promote` once and not `set_confidence`; when `promote` returns `None` it calls `set_confidence(corroborated)`; a corroborate decision calls `set_confidence` only. Add a `@pytest.mark.pg` case to `test_loop_confidence_prior_pg.py`: a suspected loop at 0.4 promoted through `corroboration` ends at 0.7 with prior 0.4. Implement the promote-path change in `corroboration.py`. `tracking.py`, `decay.py`, `review.py` do not change; `test_tracking.py` still passes.

## Phase 4: Loop postures (184 code) [US3]

- [ ] T013 [ENG] [BACKEND] Tests first in `core/arbitration/ze-priority/tests/test_scoring.py`: the loop `PriorityItem` signal carries `confidence_prior`. Add `LoopSignal.confidence_prior: float | None = None`; fill in `scoring.py`.
- [ ] T014 [ENG] [BACKEND] Tests first in `core/arbitration/ze-priority/tests/compose/test_rules_slipping.py` (replace `assert claim.confidence_from is None` for loops) and `test_composer.py` (replace the `"confidence_from" not in card["claim"]` assertion for loops; keep it for hypotheses, goals, workflows): a loop with prior 0.7 yields `confidence_from == 0.7`; a loop with null prior omits it. Implement in `compose/rules.py::_loop_posture` and `_loop_card_from_item`, and in `TurnSurfacing.mention_cards` if T001(e) found its own constructor.

## Phase 5: Hypotheses [US4]

- [ ] T015 [ENG] [BACKEND] Tests first in `core/cognition/ze-correlation/tests/test_store.py`: `list_for_display` SQL per state (open, confirmed, dismissed, all), entity filter, limit, order; `set_feedback` returns the row, accepts `None` (clear), raises `HypothesisNotFoundError` (now a `ZeError`) on none; `list_unsurfaced`, `list_recent` and `list_by_entities` (default) exclude `not_relevant` and `muted`; `list_by_entities(include_dismissed=True)` does not. Plus `apps/ze-api/tests/pg/test_hypothesis_list_pg.py` (`@pytest.mark.pg`): seeded rows cover the four states (including a confirmed row with `muted` feedback, which lists as confirmed), the entity filter, and `list_unsurfaced`/`list_recent`/`list_by_entities` skipping a muted row and showing it again after clearing. Implement in `ze_correlation/store.py`; `HypothesisNotFoundError` subclasses `ZeError`. Update `plugins/ze-personal/ze_personal/jobs/social_cooccurrence.py:161` to pass `include_dismissed=True` and add one test there; `social/tools.py:63` keeps the default (one test: a muted hypothesis is not offered).
- [ ] T016 [JR] [BACKEND] Tests first `core/cognition/ze-correlation/tests/test_rest.py`: `list_hypotheses` maps fields, resolves names with one `entity_names` call per page, returns `name: None` for a missing entity, skips and logs a row whose `claim_kind` is not inference/suspicion; `set_feedback` returns the mapped row. Implement `ze_correlation/rest.py`.
- [ ] T017 [JR] [BACKEND] Tests first `apps/ze-api/tests/api/test_hypotheses_route.py`: entity filter returns two of three (US4 independent test); `state` enum; `limit` clamp 1..200; feedback 200 / 404 / 422, `{"feedback": null}` clears; no API key → 401. (ENG regenerates the client after merge.) Implement `apps/ze-api/ze_api/api/v0/hypotheses/{__init__,router,schemas}.py` (`listHypotheses`, `setHypothesisFeedback`), `deps.get_hypothesis_store`, the entity-name lookup adapter (paths from T001), register in `api/v0/__init__.py`.
- [ ] T018 [ENG] [BACKEND] Tests first in `core/cognition/ze-correlation/tests/test_push.py` and `core/arbitration/ze-priority/tests/test_view.py`: the push sweep and `PriorityView.rank()` call the store methods that carry the predicate (the SQL itself is pinned by T015's pg test). No code change expected beyond T015.

## Phase 6: Reminders [US5]

- [ ] T019 [JR] [BACKEND] Tests first in `plugins/ze-calendar/tests/test_reminder_store.py`: `list_by_status` SQL and order for `upcoming`, `overdue`, `fired`, `all`; limit; returns `(Reminder, due)` pairs with `due` read from the `fire_at <= NOW() AS due` column. Implement `ReminderStore.list_by_status`.
- [ ] T020 [JR] [BACKEND] Tests first in `plugins/ze-calendar/tests/test_api_routes.py`: `upcoming` / `overdue` / `fired` / `all`; an unsent reminder whose `fire_at` passed has `status: overdue`; missing store → `[]`; ISO with offset; no API key → 401. (ENG regenerates the client after merge.) Implement `GET /api/v0/reminders` (`listReminders`) and `ReminderItem` in `ze_calendar/api/{routes,schemas}.py`. Run `packages/ze-sdk/tests/test_plugin_boundaries.py`.

## Phase 7: Client and gates [ENG]

- [ ] T021 [ENG] [WEB] Final codegen check: `make codegen` produces no diff. Confirm `getAttentionBudget`, `listProactiveJobRuns`, `listHypotheses`, `setHypothesisFeedback`, `listReminders` exist and `listNotifications` has the new params.
- [ ] T022 [ENG] [PLATFORM] Gates: `make lint`, `make test-py`, `make test-pg`, `make typecheck-web`, `make test-web`. SC-002: `rtk proxy grep -rn "count_sent_within_hours\|window_sent_at" core apps` shows one query used only by `budget_status`. Record results in the Handoffs note.

## Phase 8: Docs [DOCS]

- [ ] T023 [DOCS] Update every doc in plan.md "Docs touched": `docs/native-interface.md`, `docs/architecture.md` (REST tables, `push_log` row), `docs/frontend.md` (quiet-hours widget), `docs/package-architecture.md` (`PushLogStore`), `core/arbitration/ze-priority/README.md` (rolling 24 h), `docs/scheduled-jobs.md`, `docs/configuration.md`, `docs/features.md`, `docs/cognitive-architecture.md` / `docs/memory.md` where they describe loop confidence, package READMEs (ze-proactive, ze-worldstate, ze-correlation, ze-calendar if present).
- [ ] T024 [DOCS] `AGENTS.md` phase row 185, migration table (`zw005`), ze-worldstate layout line; `specs/README.md` row 185 → Implemented; the 184 `claim-descriptors.md` `confidence_from` line; spec status → Implemented.
- [ ] T025 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; every changed public surface named in a doc. Record in the Handoffs note.

---

## Dependencies

- T001 before everything.
- US1: T002 → T003, T004 → T005 (T004's commit carries the regenerated client).
- US2: T006 → T007; T008 independent.
- US3: T009 → T010 → T011, T012; T010 → T013 → T014.
- US4: T015 → T016 → T017; T015 → T018.
- US5: T019 → T020.
- ENG codegen commit after each of T007, T008, T017, T020 merges. T021 after all of them. T022 after all code. T023–T025 last.

## Parallel examples

- After T001: ENG takes T002 and T009; JR takes T019 → T020 and T008.
- After T015: JR T016 → T017 while ENG does T010–T014.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001–T004, T006, T009–T015, T018, T021, T022, and the codegen commit after each JR route task. Owns `packages/ze-client/src/generated/*`.

### Lane JR (OpenCode junior)

T005, T007, T008, T016, T017, T019, T020.

### Docs (Docs Steward)

T023–T025.

### Cross-lane touch points

- `apps/ze-api/ze_api/api/v0/__init__.py`: T008 and T017 each add one router line; whoever lands second rebases.
- `apps/ze-api/ze_api/api/deps.py`: T008 and T017 add one getter each.
- `apps/ze-api/ze_api/api/v0/notifications/{router,schemas}.py`: T004 (ENG) before T007 (JR).
