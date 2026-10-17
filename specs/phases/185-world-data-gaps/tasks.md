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
- `get_logger(__name__)`; typed `ZeError` subclasses; no bare `Exception`/`ValueError` raised in domain code.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [BACKEND] Branch from `main` with 184 merged. `graphify update .`, then `graphify affected` on `within_budget`, `PushLogStore`, `ProactiveNotifier`, `NotificationStore`, `QuietHoursResponse`, `JobRunStore`, `PostgresLoopStore`, `OpenLoop`, `LoopSignal`, `PostgresHypothesisStore`, `ReminderStore`, `_loop_to_list_item`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) the `zw` chain head (expect `zw004`); (c) every caller of `remaining_budget`; (d) the container attribute paths for `job_run_store`, the hypothesis store and the memory store's `get_entities_by_ids`; (e) whether `TurnSurfacing.mention_cards` builds loop postures through `compose/rules.py` helpers or its own constructor. Stop and report differences to the Spec Architect.

## Phase 1: Budget [US1]

- [ ] T002 [ENG] [BACKEND] Tests first in `core/contracts/ze-proactive/tests/test_attention_budget.py` (rename fakes' `count_sent_within_hours` to `window_stats` returning `(count, oldest)`): `budget_status` returns used/remaining; `next_slot_at` = oldest + 24 h only when `remaining == 0`; `budget_status` raises on store failure; `within_budget` stays fail-open; `try_claim_shared` behaviour unchanged. Add `BudgetStatus` (`types.py`), `budget_status`, `PushLogStore.window_stats`; delete `count_sent_within_hours`; `ProactiveNotifier.remaining_budget` calls `budget_status` (falls back to max on failure). Update notifier test fakes.
- [ ] T003 [ENG] [BACKEND] `apps/ze-api/tests/pg/test_push_log_window_pg.py` (`@pytest.mark.pg`): three claims inside the window and one outside → `window_stats` returns `(3, oldest inside)`.
- [ ] T004 [ENG] [BACKEND] Tests first in `apps/ze-api/tests/api/test_notifications_route.py` and `test_quiet_hours_routes.py`: `GET /api/v0/notifications/budget` returns the seven fields from fakes (the US1 independent test); store failure → 503 with the typed error; `getQuietHours` no longer has `held_count` or `max_discretionary_per_day`. Implement `AttentionBudgetResponse`, `BudgetUnavailableError` (`ze_api/errors.py`), the route (`getAttentionBudget`, summary, description), and the `QuietHoursResponse` cut.
- [ ] T005 [JR] [WEB] After T004 and `make codegen`: `apps/ze-web/src/entities/notification/api/useAttentionBudgetQuery.ts` (exported from `entities/notification/index.ts`); `widgets/settings-workspace/ui/QuietHoursSettings.tsx` and its test read `max_per_day` and `held_count` from it; `pages/jarvis/model/world.ts` likewise. `make typecheck-web`, `make test-web`.

## Phase 2: Push outcomes and job runs [US2]

- [ ] T006 [ENG] [BACKEND] Tests first in `core/contracts/ze-proactive/tests/test_notification_store.py`: `list_page(delivery=["held","suppressed"], push_class="discretionary", since=t)` builds one parameterized WHERE with all three conditions and the cursor; no filters → today's SQL. `Notification` gains `delivered_at`. Implement.
- [ ] T007 [JR] [BACKEND] Tests first in `apps/ze-api/tests/api/test_notifications_route.py`: `delivery=held&delivery=suppressed` reaches the store as a list; an unknown delivery value → 422; items carry `urgency` and `delivered_at`. Implement the `listNotifications` query params (Literal types for the zpro004 enums) and `NotificationItem` fields in `apps/ze-api/ze_api/api/v0/notifications/{router,schemas}.py`.
- [ ] T008 [JR] [BACKEND] Tests first `apps/ze-api/tests/api/test_proactive_job_runs_route.py` (fake `JobRunStore.get_all`): sorted by `last_started_at` desc; `since` filters; status enum. Implement `apps/ze-api/ze_api/api/v0/proactive/{__init__,router,schemas}.py` (`listProactiveJobRuns`), `deps.get_job_run_store` (path from T001), register in `api/v0/__init__.py`.

## Phase 3: Loop confidence movement [US3]

- [ ] T009 [ENG] [PLATFORM] `core/cognition/ze-worldstate/ze_worldstate/migrations/versions/zw005_loop_confidence_prior.py` (revision `zw005`, down `zw004`; upgrade adds both nullable columns, downgrade drops them). Extend the migration-chain test if one lists `zw` heads (grep `zw004` in `apps/ze-api/tests`).
- [ ] T010 [ENG] [BACKEND] Tests first `apps/ze-api/tests/pg/test_loop_confidence_prior_pg.py` (`@pytest.mark.pg`, `_builders.make_loop`): `set_confidence` from 0.4 to 0.55 stamps prior 0.4 and a timestamp; the same value again leaves both unchanged; `stamp_declared` stamps; `promote` with a lower confidence argument (GREATEST keeps the old value) stamps nothing; a fresh loop has nulls; `get` and `list` return the fields. Implement the shared SQL fragment in `PostgresLoopStore.set_confidence`, `stamp_declared`, `promote`; `OpenLoop` fields; `_loop_from_row`.
- [ ] T011 [ENG] [BACKEND] Tests first in `core/cognition/ze-worldstate/tests/test_rest.py`: list items carry `confidence_prior`, `confidence_changed_at`, `drift_deadline`, `confirmed_at` (ISO or null). Implement `_loop_to_list_item` and `apps/ze-api/ze_api/api/v0/loops/schemas.py::LoopListItem`.
- [ ] T012 [ENG] [BACKEND] Unit tests in `test_corroboration_flow.py` and `test_tracking.py` still pass with no change to `corroboration.py`, `tracking.py`, `decay.py`, `review.py` (they call the store; nothing to edit). If any fake store needs the new `OpenLoop` fields, add defaults only.

## Phase 4: Loop postures (184 code) [US3]

- [ ] T013 [ENG] [BACKEND] Tests first in `core/arbitration/ze-priority/tests/test_scoring.py`: the loop `PriorityItem` signal carries `confidence_prior`. Add `LoopSignal.confidence_prior: float | None = None`; fill in `scoring.py`.
- [ ] T014 [ENG] [BACKEND] Tests first in `core/arbitration/ze-priority/tests/compose/test_rules_slipping.py` (replace `assert claim.confidence_from is None` for loops) and `test_composer.py` (replace the `"confidence_from" not in card["claim"]` assertion for loops; keep it for hypotheses, goals, workflows): a loop with prior 0.7 yields `confidence_from == 0.7`; a loop with null prior omits it. Implement in `compose/rules.py::_loop_posture` and `_loop_card_from_item`, and in `TurnSurfacing.mention_cards` if T001(e) found its own constructor.

## Phase 5: Hypotheses [US4]

- [ ] T015 [ENG] [BACKEND] Tests first in `core/cognition/ze-correlation/tests/test_store.py`: `list_for_display` SQL per state (open, confirmed, dismissed, all), entity filter, limit, order; `set_feedback` returns the row and raises `HypothesisNotFoundError` on none; `list_unsurfaced` and `list_recent` SQL now exclude `not_relevant` and `muted`. Implement in `ze_correlation/store.py`.
- [ ] T016 [JR] [BACKEND] Tests first `core/cognition/ze-correlation/tests/test_rest.py`: `list_hypotheses` maps fields, resolves names with one `entity_names` call per page, returns `name: None` for a missing entity, skips and logs a row whose `claim_kind` is not inference/suspicion; `set_feedback` returns the mapped row. Implement `ze_correlation/rest.py`.
- [ ] T017 [JR] [BACKEND] Tests first `apps/ze-api/tests/api/test_hypotheses_route.py`: entity filter returns two of three (US4 independent test); `state` enum; `limit` clamp 1..200; feedback 200 / 404 / 422. Implement `apps/ze-api/ze_api/api/v0/hypotheses/{__init__,router,schemas}.py` (`listHypotheses`, `setHypothesisFeedback`), `deps.get_hypothesis_store`, the entity-name lookup adapter (paths from T001), register in `api/v0/__init__.py`.
- [ ] T018 [ENG] [BACKEND] Tests first in `core/cognition/ze-correlation/tests/test_push.py` and `core/arbitration/ze-priority/tests/test_view.py`: a fake store that honours the feedback predicate yields no muted hypothesis to the push sweep or to `PriorityView.rank()`. No code change expected beyond T015; this pins the behaviour.

## Phase 6: Reminders [US5]

- [ ] T019 [JR] [BACKEND] Tests first in `plugins/ze-calendar/tests/test_reminder_store.py`: `list_by_status` SQL and order per status; limit. Implement `ReminderStore.list_by_status`.
- [ ] T020 [JR] [BACKEND] Tests first in `plugins/ze-calendar/tests/test_api_routes.py`: `upcoming` / `fired` / `all`; `status` derived from `sent`; missing store → `[]`; ISO with offset. Implement `GET /api/v0/reminders` (`listReminders`) and `ReminderItem` in `ze_calendar/api/{routes,schemas}.py`. Run `packages/ze-sdk/tests/test_plugin_boundaries.py`.

## Phase 7: Client and gates [ENG]

- [ ] T021 [ENG] [WEB] `make codegen`; commit `packages/ze-client/src/generated/*`. Confirm `getAttentionBudget`, `listProactiveJobRuns`, `listHypotheses`, `setHypothesisFeedback`, `listReminders` exist and `listNotifications` has the new params.
- [ ] T022 [ENG] [PLATFORM] Gates: `make lint`, `make test-py`, `make test-pg`, `make typecheck-web`, `make test-web`. SC-002: `rtk proxy grep -rn "count_sent_within_hours\|window_stats" core apps` shows one query used only by `budget_status`. Record results in the Handoffs note.

## Phase 8: Docs [DOCS]

- [ ] T023 [DOCS] Update every doc in plan.md "Docs touched": `docs/native-interface.md`, `docs/scheduled-jobs.md`, `docs/configuration.md`, `docs/features.md`, `docs/cognitive-architecture.md` / `docs/memory.md` where they describe loop confidence, package READMEs (ze-proactive, ze-worldstate, ze-correlation, ze-calendar if present).
- [ ] T024 [DOCS] `AGENTS.md` phase row 185, migration table (`zw005`), ze-worldstate layout line; `specs/README.md` row 185 → Implemented; the 184 `claim-descriptors.md` `confidence_from` line; spec status → Implemented.
- [ ] T025 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; every changed public surface named in a doc. Record in the Handoffs note.

---

## Dependencies

- T001 before everything.
- US1: T002 → T003, T004 → T005 (needs codegen from T004's schema; run `make codegen` locally first, commit in T021).
- US2: T006 → T007; T008 independent.
- US3: T009 → T010 → T011, T012; T010 → T013 → T014.
- US4: T015 → T016 → T017; T015 → T018.
- US5: T019 → T020.
- T021 after T004, T007, T008, T011, T017, T020. T022 after all code. T023–T025 last.

## Parallel examples

- After T001: ENG takes T002 and T009; JR takes T019 → T020 and T008.
- After T015: JR T016 → T017 while ENG does T010–T014.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001–T004, T006, T009–T015, T018, T021, T022.

### Lane JR (OpenCode junior)

T005, T007, T008, T016, T017, T019, T020.

### Docs (Docs Steward)

T023–T025.

### Cross-lane touch points

- `apps/ze-api/ze_api/api/v0/__init__.py`: T008 and T017 each add one router line; whoever lands second rebases.
- `apps/ze-api/ze_api/api/deps.py`: T008 and T017 add one getter each.
- `apps/ze-api/ze_api/api/v0/notifications/{router,schemas}.py`: T004 (ENG) before T007 (JR).
