---

description: "Tasks for phase 204 Push Bar and Cooldowns"
---

# Tasks: Push Bar and Cooldowns

**Input**: Design documents from `specs/phases/204-push-bar-and-cooldowns/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required (constitution V; spec SC-002, SC-003, SC-004, SC-006). Each story begins with a test that fails on today's code, through the real interface. SQL-backed behaviour has a test-pg test in `apps/ze-api/tests/pg/` (`pytestmark = pytest.mark.pg`, `pg_pool` fixture, `make test-pg`). No real model call.

**Organization**: Tasks are grouped by user story (spec.md US1–US5).

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Lane]**: The crew lane from plan.md's Lane Plan that owns this task: `[L:lead]`, `[L:bar]`, `[L:conv]`, `[L:jobs]`, `[L:jr1]`, `[L:docs]`. A task touches only files its lane owns.
- **[Story]**: The user story (US1–US5)
- **Tags**: [BE] backend, [PLATFORM] migrations, wiring and gates, [DOCS] documentation

**Crew**: Sonnet for `lead`, `bar`, `conv` and `jobs`; Haiku for `jr1` and `docs`. The contract step (T001–T005, `[L:lead]`) lands first. The other code lanes then run in parallel in their own worktrees, and each is reviewed as it finishes.

**Rules for every lane**: tick a task's checkbox in the same commit that finishes it. Run `graphify affected "<Symbol>" --depth 2` before you change a public symbol, and update every caller your lane owns in the same change; list callers in other lanes' files in the Handoffs note for `lead`. Never call `json.loads` on a model reply, never use `print()`, raise typed `ZeError` subclasses only.

---

## Phase 1: Setup

- [x] T001 [L:lead] [PLATFORM] Confirm on main that `zpro005` is the head of `core/contracts/ze-proactive/ze_proactive/migrations/versions/` and `zpri001` the head of `core/arbitration/ze-priority/ze_priority/migrations/versions/`, and that no open spec claims `zpro006` or `zpri002` (`grep -rn "zpro006\|zpri002" specs/phases`). Record `zpro006_push_claims.py` and `zpri002_surfacing_memory.py` in the "204 Handoffs" note.

---

## Phase 2: Foundational (contract step)

**Purpose**: The ze-proactive public surface every lane builds against ([contracts/notifier.md](contracts/notifier.md)). Other lanes start when T005 is merged into the floor branch.

- [x] T002 [L:lead] [BE] Write failing tests in a new `core/contracts/ze-proactive/tests/test_once_per.py`: `OncePer("")` and `OncePer("k", within=timedelta(0))` raise `PushPolicyError`; `OncePer("k")` has `within is None`; `is_sent` is true only for `delivered` and `held` (parametrize over all five outcomes and `None`). Then, in `core/contracts/ze-proactive/ze_proactive/types.py`, add `OncePer` (frozen dataclass, validation in `__post_init__`), `is_sent`, and remove `"duplicate"` from `PushOutcome`.
- [x] T003 [P] [L:lead] [BE] Create `core/contracts/ze-proactive/ze_proactive/candidates.py` with the frozen dataclasses `BarThresholds` and `PushCandidate`, fields exactly as in data-model.md, and a test in `core/contracts/ze-proactive/tests/test_candidates.py` that builds one of each.
- [x] T004 [L:lead] [BE] Change `ProactiveNotifier` (`core/contracts/ze-proactive/ze_proactive/notifier.py`) to the contract signature: `notify(..., once_per: OncePer | None = None, ...)` with `budget_key` and `dedup_hours` removed; `PushPolicyError` for a discretionary push without `once_per` and for a requested push with one; new `on_cooldown(once_per)` and `recent_discretionary_bodies(hours)`. Add `core/contracts/ze-proactive/ze_proactive/testing.py` with `InMemoryPushLog`, an in-memory implementation of the private store contract (`claim`, `release`, `is_cooling`, `window_sent_at`, `recent_discretionary_payloads`) that takes a `clock` callable, so lanes can test with a real notifier. Delete `NotificationStore.exists_recent` (`notification_store.py:308-330`) and its tests in `tests/test_notification_store.py`. Update `tests/test_notifier.py` call sites from `budget_key=` to `once_per=OncePer(...)` and assert the two policy errors.
- [x] T005 [L:lead] [BE] In `packages/ze-sdk/ze_sdk/proactive.py`, export `OncePer` and `is_sent` and remove `PushLogStore` and `PushLogEntry`; update the export lists and any test in `packages/ze-sdk/tests/` that names them. `make test-proactive test-sdk`. Merge to the floor branch and announce "contract ready" in the Handoffs note.

**Checkpoint**: the contract types and the `notify` signature exist; lanes `bar`, `conv`, `jobs` and `jr1` start.

---

## Phase 3: User Story 1 - A push Ze already sent is not sent again, and a failed one is retried (Priority: P1) 🎯 MVP

**Goal**: one claim rule in the governor (FR-005, FR-006, FR-007, FR-009, FR-013, FR-014, FR-016); every caller migrated.

**Independent Test**: `make test-proactive test-automation test-personal test-calendar test-finance test-messenger`, `make test -k cooldown_jobs` and `make test-pg -k push_claims`.

### Governor (lane `lead`)

- [x] T006 [L:lead] [US1] [PLATFORM] Write failing test-pg tests in a new `apps/ze-api/tests/pg/test_push_claims_pg.py` per [contracts/migrations-and-failures.md](contracts/migrations-and-failures.md): a second `claim` of one key inside `within` is `cooling`; with `sent_at` moved outside the window (raw `UPDATE`), `won`; `within=None` cools forever; discretionary claims reach `over_budget` at the cap and insert nothing; accountability claims never count against the budget; `release(claim_id)` frees the key; `asyncio.gather` of two `claim` calls on one key gives exactly one `won`; `recent_discretionary_payloads` returns only discretionary payloads in the window; claims of two different keys inside one window both win (spec edge case). The upgrade itself is checked in T041. Delete `apps/ze-api/tests/pg/test_push_log_window_pg.py`.
- [x] T007 [L:lead] [US1] [PLATFORM] Create `core/contracts/ze-proactive/ze_proactive/migrations/versions/zpro006_push_claims.py` (`revision = "zpro006"`, `down_revision = "zpro005"`), raw SQL exactly as in contracts/migrations-and-failures.md, with the downgrade described there. Keep the step-1 `DELETE` as a module constant `DELETE_NON_CLAIMS_SQL` so T041 can quote it.
- [x] T008 [L:lead] [US1] [BE] Rewrite `core/contracts/ze-proactive/ze_proactive/push_log_store.py` to the private contract: `ClaimResult`, `claim` (one transaction: key advisory lock, then the budget lock when discretionary, cooldown check, budget count, insert; research R2), `release`, `is_cooling`, `window_sent_at(hours)` (discretionary only), `recent_discretionary_payloads(hours)`. Delete `was_sent_within_hours`, `log`, `try_claim`, `release_claim`, `list_recent_payloads`, `list_workflow_failures_within_hours` and `PushLogEntry`. In `attention_budget.py`, keep `budget_status` (now `push_log.window_sent_at(window_hours)`) and delete `ATTENTION_PUSH_EVENT_KEY`, `within_budget`, `try_claim_shared` and `release_shared`. Rewrite `tests/test_push_log_store.py` and `tests/test_attention_budget.py` for the new surface. T006 passes.
- [x] T009 [L:lead] [US1] [BE] Write a failing test `core/contracts/ze-proactive/tests/test_notifier_once_per.py` (SC-002), using `InMemoryPushLog` and a fake interface: parametrize over the governor outcomes (`failed` from a push that raises, `failed` from a persist error, `suppressed_budget`, `held`, `delivered`) and assert the next `notify` with the same `OncePer` returns `deduped` only after `held` or `delivered`; `deduped` creates no notification row; a requested push takes no claim; a claim-store error lets the push through and logs `push_claim_failed`; `deliver_held` never claims, and a failed release keeps the claim (FR-016). Then implement the flow in `notifier.py` per the contract table (claim → decide → persist → deliver → release by id on `failed`). `make test-proactive`.
- [x] T010 [L:lead] [US1] [BE] Add `build_notifier(pool, interface, notification_store, settings_store, settings)` to `core/contracts/ze-proactive/ze_proactive/bootstrap.py` (builds the `PushLogStore`; max from `shared_push_budget`). Rename `interruption_data_domains` to `proactive_data_domains` in `data_domain.py` and add the `proactive.log` domain (export, delete, import, count, size over `push_log`) there; delete the `_engine_domain("proactive.log", "push_log")` line from `core/engine/ze-core/ze_core/bootstrap.py:256`. Tests in `core/contracts/ze-proactive/tests/`. `make test-proactive test-core`.

### Cooldown jobs and ze-automation callers (lane `jobs`)

- [ ] T011 [L:jobs] [US1] [BE] Write a failing test `apps/ze-api/tests/test_cooldown_jobs.py`, parametrized over `AccountabilityJob`, `GoalNarrativeJob`, `MorningBriefing` and the workflow-failure handler (`make_workflow_failure_handler`). Each uses a real `ProactiveNotifier` with `InMemoryPushLog` and a fake interface whose first push raises and whose later pushes succeed; stores are `AsyncMock`s that give each job something to send. Assert: run 1 → `failed`, no claim; run 2 → one delivery; run 3 inside the window → no delivery (US1 scenarios 1-2); a budget-free `held` run (quiet hours on through a fake settings store) blocks the next run inside the window (scenario 4). Add one case per job where a claim already exists before the run, and assert the expensive builder (`GoalPlanner.synthesize_weekly_narrative`, the accountability cost query, the brief's news section) is not called (research R9).
- [ ] T012 [L:jobs] [US1] [BE] `core/automation/ze-automation/ze_automation/jobs/accountability.py`: replace the push-log cooldown with `notifier.on_cooldown(OncePer("weekly_accountability", within=timedelta(days=6)))` before building, and `notify(..., once_per=...)` with the same value; log `accountability_job_skipped_cooldown`. The constructor takes `workflow_store: WorkflowStore` in place of `push_log_store`, and `_build_summary` reads failures with `self._workflow_store.list_failed_executions(period_days * 24)` (FR-011; needs T028). Update `tests/proactive_jobs/test_accountability.py`.
- [ ] T013 [P] [L:jobs] [US1] [BE] `core/automation/ze-automation/ze_automation/jobs/goal_narrative.py`: same change with `OncePer("goal_narrative", within=timedelta(hours=144))`; the constructor loses `push_log_store`. Update `tests/proactive_jobs/test_goal_narrative.py`.
- [ ] T014 [L:jobs] [US1] [BE] `plugins/ze-personal/ze_personal/jobs/briefing.py` (`MorningBriefing`): same change with `OncePer("morning_brief", within=timedelta(hours=20))`, `is_sent` for the `briefing_sent` log; the constructor loses `push_log_store`, and `run` reads failures with `self._workflows.list_failed_executions(24)`, printing `workflow_name` and `failed_at` in the existing line (FR-011; needs T028). `plugins/ze-personal/ze_personal/plugin.py`: drop the `push_log_store` constructor parameter and the import of `ze_proactive.push_log_store`. Update `plugins/ze-personal/tests/jobs/test_briefing.py`.
- [ ] T015 [L:jobs] [US1] [BE] `core/automation/ze-automation/ze_automation/bootstrap.py`: `make_workflow_failure_handler` loses `push_log_store` and the `workflow_failure:<id>` ledger write, and alerts with `once_per=OncePer(f"workflow_failure_alert:{workflow.id}", within=timedelta(hours=cooldown))`; `configure_workflow_executor` and `register_proactive_jobs` lose `push_log_store`; `AccountabilityJob` is built with `workflow_store`. Update `tests/workflow_engine/test_failure_handler.py`, `test_configure_executor.py` and `test_scheduler_catchup.py`.
- [ ] T016 [L:jobs] [US1] [BE] Replace `budget_key=X` with `once_per=OncePer(X)` and the outcome check with `is_sent(outcome)` in `ze_automation/jobs/stuck_goals.py:47,50`, `jobs/goal_suggestion.py:126`, `goals/proposal.py:166` and `goals/executor.py:802` (keys unchanged, no window; contracts/notifier.md). Update `tests/proactive_jobs/test_stuck_goals.py`, `test_goal_suggestion.py`, `tests/goal_agent/test_create_goal_convergence.py` and `tests/goal_engine/test_executor_reuse_notice.py`. `make test-automation`.

### Plugin callers (lane `jr1`)

- [ ] T017 [P] [L:jr1] [US1] [BE] `plugins/ze-finance/ze_finance/jobs/recurring.py`: at lines 111, 133 and 151 replace `budget_key=<expr>` with `once_per=OncePer(<expr>)` (same expression); at line 113 replace `if outcome in ("delivered", "held"):` with `if is_sent(outcome):`. Import both from `ze_sdk.proactive`. In `plugins/ze-finance/tests/test_recurring_job.py`, change each assertion on `budget_key` to `once_per == OncePer(<same key>)`. `make test-finance`.
- [ ] T018 [P] [L:jr1] [US1] [BE] `plugins/ze-messenger/ze_messenger/inbound/processor.py:153`: `budget_key=f"inbound:{msg.channel_type}:{msg.message_id}"` → `once_per=OncePer(f"inbound:{msg.channel_type}:{msg.message_id}")`, import from `ze_sdk.proactive`. Update the `budget_key` assertions in `plugins/ze-messenger/tests/test_inbound_relay_push.py` the same way. `make test-messenger`.
- [ ] T019 [P] [L:jr1] [US1] [BE] `plugins/ze-personal/ze_personal/jobs/insights.py:171,173`: `budget_key=f"insight:{row['id']}"` → `once_per=OncePer(f"insight:{row['id']}")` and `if outcome in ("delivered", "held"):` → `if is_sent(outcome):`. `plugins/ze-personal/ze_personal/jobs/contacts.py:55`: `budget_key=f"contact:{pid}"` → `once_per=OncePer(f"contact:{pid}")`. Import from `ze_sdk.proactive`. Update `plugins/ze-personal/tests/jobs/test_insights.py` and `plugins/ze-personal/tests/jobs/test_contact_review.py`. `make test-personal`.
- [ ] T020 [P] [L:jr1] [US1] [BE] ze-calendar (FR-012): in `plugins/ze-calendar/ze_calendar/reminders/calendar.py`, delete `await self._push_log.log(f"calendar_reminder:{reminder_id}", label)` (line 193), the `push_log_store` constructor parameter, the `self._push_log` attribute and the `PushLogStore` import; in `plugins/ze-calendar/ze_calendar/plugin.py`, delete the `push_log_store` parameter (line 34), `self._push_log_store` (line 42), the argument at line 150 and the import at line 14. In `plugins/ze-calendar/tests/jobs/test_reminders.py`, remove `push_log_store=` from `make_reminder_service`, remove the `push_log.log` assertion from `test_fire_reminder_pushes_and_logs`, and delete the local `make_failure_handler` and the three `test_workflow_failure_alert_*` tests (they test a local copy; the real handler is covered by ze-automation's `test_failure_handler.py`). `make test-calendar`.

**Checkpoint**: every push goes through one claim rule; `make test-proactive test-automation test-personal test-calendar test-finance test-messenger` and `make test-pg -k push_claims` are green in their lanes.

---

## Phase 4: User Story 2 - Every discretionary push passes the same bar, with the same inputs (Priority: P1)

**Goal**: one `PushBar`, applied by arbitration; loops and hypotheses are candidate sources (FR-001–FR-004, SC-003, SC-005).

**Independent Test**: `make test-priority test-worldstate test-correlation`.

- [ ] T021 [L:bar] [US2] [BE] Write failing tests in a new `core/arbitration/ze-priority/tests/test_push_bar.py` against [contracts/push-bar.md](contracts/push-bar.md), with a fake embedder (dict of fixed vectors), a fake NLI (fixed `scores`/`grounding_score`), a fake `PushHistory` and a fake `MentionRecency`: one test per reason (`low_confidence`, `irrelevant`, `mentioned_recently`, `not_novel`, `ungrounded`) and its order (a candidate failing two conditions reports the earlier); `relevance` and `evidence_labels` are thunks: a candidate failing on confidence never calls either, and `evidence_labels` is called only at the grounding step (assert with counting fakes); a `relevance` thunk that raises rejects the candidate as `irrelevant`; `inline_cooldown_hours=None` skips the mention check; empty evidence skips grounding; an exception in each check passes it and logs `push_bar_<condition>_check_failed`; history is read once per `screen` call for three candidates; `PushBar(embedder=…, history=…, mentions=…)` without `nli` raises `TypeError`; `nli=None` logs `push_bar_grounding_off` once and skips grounding (US2 scenario 4); a candidate with a `source_kind` the code has never seen (`"test_kind"`) is screened like any other (SC-005).
- [ ] T022 [L:bar] [US2] [BE] Create `core/arbitration/ze-priority/ze_priority/push_bar.py` (`PushHistory`, `MentionRecency`, `BarReason`, `BarVerdict`, `PushBar`), moving the cosine and NLI formulas from `ze_correlation/push.py:41-88`. Add `ze-proactive` to `core/arbitration/ze-priority/pyproject.toml` (dependencies and `[tool.uv.sources]`) and refresh `uv.lock` (`uv lock`). T021 passes.
- [ ] T023 [L:bar] [US2] [BE] Turn `LoopSurfacer` (`core/cognition/ze-worldstate/ze_worldstate/surfacing.py`) into a candidate source per the contract: keyword constructor without `push_log`, `embedder` and `nli_client`; `source_kind`, `dry_run`, `thresholds`, `candidates()` (each candidate carries `once_per=OncePer(f"loop:{id}", within=timedelta(days=settings.repush_after_days))` and thunks for `relevance` and `evidence_labels`, data-model.md), `send()` (re-check drifting; `notify(..., once_per=candidate.once_per)`); delete `passes_push_bar`, `eligible_candidates` and the `ze_correlation.push` and `ze_proactive.attention_budget` imports. In `ze_worldstate/bootstrap.py`, add `repush_after_days: float = 7.0` to `LoopPushSettings` (read from `worldstate.push.repush_after_days`) and `bar_thresholds()`, and change `build_loop_surfacer(stack, relevance_model, notifier, settings)`. Remove `ze-correlation` from `core/cognition/ze-worldstate/pyproject.toml` and refresh `uv.lock`. Rewrite `core/cognition/ze-worldstate/tests/test_surfacing.py` (candidate fields from data-model.md, send re-check, the `OncePer` value) and update `tests/test_bootstrap.py`. `make test-worldstate`.
- [ ] T024 [P] [L:bar] [US2] [BE] Turn `CorrelationPushCandidateSource` (`core/cognition/ze-correlation/ze_correlation/push.py`) into a candidate source per the contract (thresholds from `_load_config` and `nli_config`, `inline_cooldown_hours=None`, `dry_run` from config, candidates carry `once_per=OncePer(f"hypothesis:{id}")` and wrap `relevance` and the evidence labels in thunks; `send` uses `candidate.once_per` and `is_sent`); delete `passes_confidence`, `passes_relevance`, `passes_novelty`, `passes_grounding`, the private bar methods and `_NOVELTY_LOOKBACK_HOURS`. `ze_correlation/bootstrap.py`: `build_correlation_push_candidate_source(stack, notifier, settings)`. `ze_correlation/store.py`: delete `list_recently_surfaced_summaries`. Rewrite `core/cognition/ze-correlation/tests/test_push.py` (candidates, disabled → `[]`, send marks surfaced only when sent) and fix `tests/test_hypothesis_decay.py` if it names a deleted symbol. `make test-correlation`.
- [ ] T025 [L:bar] [US2] [BE] Write failing tests in `core/arbitration/ze-priority/tests/test_arbitration.py` that drive only `AttentionArbitrationJob.run` (SC-003), with a real `PushBar` (fake embedder and NLI), fake sources and a fake notifier: `test_bar_rejects_ungrounded_and_repeated_loop` (one loop rejected `ungrounded`, one `not_novel` against a history body pushed 3 hours ago; nothing sent; `push_bar_rejected` logged with the reason; US2 scenarios 1-2); `test_loop_and_hypothesis_share_history` (scenario 3); `test_inline_mention_blocks_push` (US4 scenario 1, fake `MentionRecency`); a dry-run source sends nothing; ranking order via `rank_subset`; stop on `held`/`delivered`/`suppressed_budget`, continue on `deduped`/`failed`/`None`; `remaining_budget() == 0` reads no candidates; a candidate whose `once_per` is cooling (`notifier.on_cooldown` true) is never screened and is logged `push_candidate_cooling`; three fake sources of three kinds are screened and sent through the same path, each `send` going to its own source (SC-005: the job has no branch on `source_kind`). Delete the tests of the old `loop_push`/`eligible_candidates` shape.
- [ ] T026 [L:bar] [US2] [BE] Rewrite `core/arbitration/ze-priority/ze_priority/arbitration.py` to the contract (`sources`, `bar`, `notifier`, `priority_view`; `is_sent`; no `LoopPushSettings` import). T025 passes. `make test-priority`.
- [ ] T027 [L:bar] [US2] [BE] Add `repush_after_days: 7` under `worldstate.push` in `apps/ze-api/config/config.yaml` and to the exact key set in `apps/ze-api/tests/test_shipped_config_keys.py`. Update `apps/ze-api/tests/pg/test_acceptance.py` and `apps/ze-api/tests/pg/test_loop_evidence.py` to build `LoopSurfacer` with the new constructor and assert on `candidates()` instead of `eligible_candidates()`.

**Checkpoint**: `make test-priority test-worldstate test-correlation` green; the bar has one implementation.

---

## Phase 5: User Story 3 - The workflow-failure history survives without the push log (Priority: P2)

**Goal**: failures are read from `workflow_executions` (FR-011, SC-004).

**Independent Test**: `make test-automation test-personal` and `make test-pg -k workflow_failures`.

- [ ] T028 [L:jobs] [US3] [BE] Write a failing test-pg test in a new `apps/ze-api/tests/pg/test_workflow_failures_pg.py` (the harness does not truncate workflow tables: use fresh UUIDs and assert only on your own rows and their relative order): insert a workflow and three executions (two `failed` 10 and 30 minutes ago, one `completed`) plus one `failed` 3 days ago and one `failed` with `workflow_id` NULL; `PostgresWorkflowStore(pool).list_failed_executions(24)` includes the three recent failures newest first, the orphan named `"unknown"`, and excludes the old and the completed run. Add a run marked `failed` by `recover_stale` (no failure handler ran): it is listed (research R7). Then add `WorkflowFailure` to `core/automation/ze-automation/ze_automation/workflow/types.py`, the method to the `WorkflowStore` Protocol (`workflow/store.py`) and `PostgresWorkflowStore` (`workflow/postgres.py`), SQL as in contracts/migrations-and-failures.md.
- [ ] T029 [L:jobs] [US3] [BE] Write a failing test in a new `core/automation/ze-automation/tests/test_status_summary.py`: `build_status_summary` with a fake container whose `workflow_store.list_failed_executions` returns two failures of one workflow (only one of which was alerted) lists both (US3 scenario 1, SC-004). Then change `core/automation/ze-automation/ze_automation/rest.py` (`build_status_summary`) to read `container.workflow_store.list_failed_executions(period_days * 24)` and use `workflow_name`; delete the `PushLogStore` import.
- [ ] T030 [L:jobs] [US3] [BE] Add tests that the weekly accountability report (`core/automation/ze-automation/tests/proactive_jobs/test_accountability.py`) and the morning brief (`plugins/ze-personal/tests/jobs/test_briefing.py`) list two failures of one workflow when `list_failed_executions` returns them, whether or not an alert went out (the reads changed in T012 and T014). `make test-automation test-personal`.

**Checkpoint**: `/status`, the weekly report and the brief list every failed run.

---

## Phase 6: User Story 5 - A loop that keeps drifting is pushed again, at most weekly (Priority: P2)

**Goal**: FR-015, SC-006.

**Independent Test**: `make test-priority -k repush`.

- [ ] T031 [L:bar] [US5] [BE] Add `test_loop_repush_after_window` to `core/arbitration/ze-priority/tests/test_arbitration.py`: a real `ProactiveNotifier` with `InMemoryPushLog` and a controllable clock, a real `LoopSurfacer` over fake stores returning one drifting loop (`repush_after_days=7`), a bar whose fakes pass everything. Run 1 pushes; with the clock 6 days later, `send` returns `deduped` and nothing is delivered; 8 days later the loop is pushed again. Passes with T023 and T026; if not, fix in `surfacing.py`.

---

## Phase 7: User Story 4 - Conversation cooldowns belong to the conversation (Priority: P3)

**Goal**: inline and offer cooldowns on `TurnSurfacing`'s own record (FR-010).

**Independent Test**: `make test-priority -k turn` and `make test-pg -k "surfacing_memory or loop_confirmation"`.

- [ ] T032 [L:conv] [US4] [PLATFORM] Create `core/arbitration/ze-priority/ze_priority/migrations/versions/zpri002_surfacing_memory.py` (`revision = "zpri002"`, `down_revision = "zpri001"`), table and index as in data-model.md.
- [ ] T033 [L:conv] [US4] [BE] Write failing test-pg tests in a new `apps/ze-api/tests/pg/test_surfacing_memory_pg.py` (`surfacing_memory` joins the harness's truncated tables only in T038, so use fresh UUIDs per test): `record("inline", "loop", [a, b])` then `recorded_within("inline", "loop", a, 12)` is true, false for `"offer"`, false for another id, false once `recorded_at` is moved 13 hours back; a row moved 31 days back is deleted by the next `record`. Then create `core/arbitration/ze-priority/ze_priority/surfacing_memory.py` (`SurfacingMemory` Protocol, `PostgresSurfacingMemory`).
- [ ] T034 [L:conv] [US4] [BE] Write failing tests in `core/arbitration/ze-priority/tests/test_turn.py` with a fake `SurfacingMemory`: `inline_mentions` records loop ids (not goals or hypotheses) as `inline`; `mentioned_inline_within` reads the record; `resume_loop_offers` skips a loop offered within 168 hours, records new offers as `offer`, and returns `[]` when the read raises; `TurnSurfacing(...)` without `memory` raises `TypeError`. Then change `core/arbitration/ze-priority/ze_priority/turn.py` per the contract: required `memory`, delete the `push_log` argument and `OFFER_EVENT_PREFIX`.
- [ ] T035 [L:conv] [US4] [BE] Update `apps/ze-api/tests/pg/test_loop_confirmation_pg.py` (`test_resume_offers_are_recorded_and_cool_down_for_a_week`) to build `TurnSurfacing` with `PostgresSurfacingMemory(pg_pool)` and assert the cooldown through `surfacing_memory`, not `push_log`. `make test-priority` and `make test-pg -k "surfacing_memory or loop_confirmation"`.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T036 [L:lead] [PLATFORM] Merge the lane branches into the floor branch in the order `jr1` → `conv` → `jobs` → `bar`. The lanes are disjoint; resolve nothing by hand in another lane's files.
- [ ] T037 [L:lead] [PLATFORM] Wire the new constructors in `apps/ze-api/ze_api/wiring/`:
  - `stores.py`: delete `CoreStores.push_log_store` and its `PushLogStore(pool=pool)`;
  - `container.py`: build the notifier with `build_notifier(...)`; build `PushBar(embedder=shared.embedder, nli=shared.nli_client, history=notifier, mentions=turn_surfacer)`; build `TurnSurfacing(..., memory=PostgresSurfacingMemory(pool))`; `build_loop_surfacer(worldstate, relevance_model, notifier, loop_push_settings(settings))`; `build_correlation_push_candidate_source(correlation, notifier, settings)`; use `proactive_data_domains(pool)`; delete `_push_log_store`, the `PushLogStore` import and the unread `configurable["loop_surfacer"]` key;
  - `agents.py`: delete the `PushLogStore` dependency-map entry;
  - `jobs.py`: the register function takes `push_bar` and `push_sources` in place of `loop_surfacer`, `correlation_push_source` and `push_log_store`, and builds `AttentionArbitrationJob(priority_view=…, sources=push_sources, bar=push_bar, notifier=…)`; `container.py` passes the loop source only when `worldstate.push.enabled` is true.
- [ ] T038 [L:lead] [PLATFORM] Update the ze-api tests the wiring change breaks: `apps/ze-api/tests/test_governor_acceptance.py` (`once_per`, `deduped`), `apps/ze-api/tests/test_container_config.py`, `test_container_script_runner.py`, `test_container_tier_judge.py`, `apps/ze-api/tests/api/test_workspace_followthrough.py`, `test_accountability_contract.py`, `test_quiet_hours_routes.py`, `apps/ze-api/tests/agents/test_bootstrap.py`, and `apps/ze-api/tests/pg/conftest.py` and `test_harness_smoke.py` (add `surfacing_memory`, `workflow_executions` and `workflows` to `RESET_TABLES`).
- [ ] T039 [L:lead] [PLATFORM] Run the full gates and record each result in the Handoffs note and the state file: `make test-py`, `make test-pg`, `make lint`.
- [ ] T040 [L:lead] [PLATFORM] Run the grep gates in quickstart.md section 3 (SC-001, FR-013, FR-014); each prints nothing. Run `graphify update .`, then `graphify affected` on `ProactiveNotifier`, `PushBar`, `LoopSurfacer`, `CorrelationPushCandidateSource`, `TurnSurfacing` and `AttentionArbitrationJob`, and confirm every caller it lists was updated. Record useful or misleading queries with `graphify save-result ... --memory-dir /Users/joaoamatos/coding/ze/graphify-out/memory`.
- [ ] T041 [L:lead] [PLATFORM] Check the upgrade on a scratch database (quickstart.md section 4): `docker exec ze-postgres-1 createdb -U ze ze_e2e_204`; run `make migrate` from the ground checkout (`/Users/joaoamatos/coding/ze`, main) with `DATABASE_URL` and `DATABASE_URL_SYNC` pointed at it; insert one `push_log` row of each old kind with psql (`attention_push` with a key, `weekly_accountability`, `worldstate_loop_inline:<uuid>`, `calendar_reminder:<uuid>`, `workflow_failure:<uuid>`); run `make migrate` from the floor; check that only the `attention_push` row remains with `claim_key` and `discretionary = true`, and check `\d push_log` and `\d surfacing_memory`. Never run it on the shared `ze` database; the user lands floors.
- [ ] T042 [P] [L:docs] [DOCS] Update the public docs from the finished diff (doc-style skill rules):
  - `docs/scheduled-jobs.md`: cooldowns are `notify(once_per=…)`, the arbitration job screens candidates through one push bar, failures come from workflow runs;
  - `docs/sdk.md`, `docs/extending-ze.md`: `OncePer` and `is_sent` replace `budget_key` and the outcome check; `PushLogStore` is gone from `ze_sdk.proactive`;
  - `docs/configuration.md`: `worldstate.push.repush_after_days`;
  - `docs/architecture.md`, `docs/cognitive-architecture.md`, `docs/package-architecture.md`: the push bar in ze-priority, `push_log` private to ze-proactive, ze-worldstate no longer depends on ze-correlation;
  - `docs/memory.md`, `docs/native-interface.md`, `docs/workflows.md`: remove push-log mentions (`budget_key`, `duplicate`, the failure ledger) or point them at the new owners;
  - READMEs: `core/contracts/ze-proactive/README.md`, `core/arbitration/ze-priority/README.md`, `core/cognition/ze-worldstate/README.md`, `core/cognition/ze-correlation/README.md`, `core/automation/ze-automation/README.md`, `packages/ze-sdk/README.md`.
- [ ] T043 [L:docs] [DOCS] Update `AGENTS.md`: the 204 phase row (Implemented, one line in the table's style); the dependency graph (`ze-worldstate` drops `ze-correlation`; `ze-priority` adds `ze-proactive`) and the layout comments that name `push.py` or `push_log`; Migration ownership: ze-proactive `push_log` claims (`zpro006`), ze-priority `surfacing_memory` (`zpri002`). Check `specs/arch/attention-arbitration.md` and add a short "Since phase 204" note where it describes the bar living in the sources.
- [ ] T044 [L:docs] [DOCS] Set spec.md `**Status**` to Implemented and the 204 Status cell in `specs/README.md`, then run the `speckit-process-after-implement` skill.
- [ ] T045 [L:docs] [DOCS] Coverage check: `git diff main...HEAD --stat -- docs/ AGENTS.md specs/README.md '*README.md'`. Confirm every file in T042–T044 appears, and list any public doc that still names a changed symbol (`grep -rn "budget_key\|push_log\|PushLogStore\|dedup_hours\|passes_novelty\|was_sent_within_hours" docs/ README.md */*/README.md */*/*/README.md`) with a reason.

---

## Dependencies & Execution Order

- **T001 → T002–T005** (contract step, `lead`). Every other code lane starts after T005 is merged.
- **`lead`**: T006 → T007 → T008 → T009 → T010, in parallel with the other lanes.
- **`jobs`**: T011 → T028 → T012 → T013 → T014 → T015 → T016 → T029 → T030. T028 comes early because T012 and T014 switch the failure reads to `list_failed_executions`.
- **`jr1`**: T017, T018, T019, T020 in any order.
- **`bar`**: T021 → T022 → T023 → T024 → T025 → T026 → T027 → T031. T025 uses the `MentionRecency` Protocol from T022, not `conv`'s code.
- **`conv`**: T032 → T033 → T034 → T035.
- **T036–T041** (`lead`) start when all four lanes are reviewed; T037 needs T010, T023, T024, T026 and T034.
- **T042–T045** (`docs`) start after T036.

## Parallel Example

After T005, five agents work at once:

```text
lead: T006 → T007 → T008 → T009 → T010
bar:  T021 → T022 → T023 → T024 → T025 → T026 → T027 → T031
conv: T032 → T033 → T034 → T035
jobs: T011 → T028 → T012 → T013 → T014 → T015 → T016 → T029 → T030
jr1:  T017, T018, T019, T020
```

## Implementation Strategy

- **MVP**: the contract step plus US1 (T001–T020): one claim rule, no cooldown after a failure, and the 198 Q4 one-push-per-life bug gone at the governor level.
- **Then** US2 (one bar), US3 (failures from runs), US5 (weekly loop re-push) and US4 (conversation memory), then wiring and gates.
- Each lane is reviewed on its own small diff before `lead` merges it.
- Phase 213 (One Scheduler) depends on this phase landing.
