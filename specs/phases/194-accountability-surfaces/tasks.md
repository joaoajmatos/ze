# Tasks: Accountability Surfaces (B4)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/rest.md](./contracts/rest.md), [quickstart.md](./quickstart.md).

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests mock asyncpg; the two SQL filters also get one `@pytest.mark.pg` test each.

**Build gate**: starts now on `main`; runs in parallel with the web floors. `zc040` is reserved for this phase (the Maestro, 2026-10-18; `down_revision = zc039`). Phase 192 also edits `wiring/container.py`: whichever floor lands second rebases it.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:ledger]`, `[L:reads]`, `[L:channels]`, `[L:jr1]`, `[L:docs]` (plan.md Lane Plan). A task touches only files its lane owns.
- **[Story]**: US1 actions, US2 collisions, US3 tier settings, US4 loops since, US5 channel status, US6 reset deletion.

**Crew**: Sonnet `lead`, `ledger`, `reads`, `channels`; Haiku `jr1` (the fully specified deletion) and `docs`. Contract step first; then the lanes run in parallel in their own worktrees; `lead` merges ledger → reads → channels → jr1. Tick a task's checkbox in the same commit that finishes it.

**Rules for every lane**: `graphify affected` and `rtk proxy grep` before changing a shared symbol; typed `ZeError`s; `get_logger(__name__)`; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [x] T001 [L:lead] Branch from `main`. `make install`; `graphify update .`; `graphify affected` on `ActionRecordStore`, `LoopStore`, `ChannelWatermarkStore`, `InboundPollingJob`, `ResetService`, `list_collisions`, `complexity_surface_config`, `resolve_agent_model`. Grep `reset_personal_state\|reset-personal-state\|ResetService` across the repo (docs, CONTRIBUTING, README, Makefile). Run `EXPLAIN` for the planned ledger query on the dev DB (research R2). Name the migration chain test file (the one asserting a single head) for T013. Record differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [x] T002 [L:lead] Tests first `apps/ze-api/tests/api/test_accountability_contract.py`: the OpenAPI export lists `listActionRecords`, `listCollisions` (product spec, not the dev spec), `getModelSettings`, `listChannelStatus`, and `listLoops` with a `since` parameter, each with its response model from [contracts/rest.md](./contracts/rest.md). Implement:
  - the schemas: `api/v0/actions/schemas.py`, `api/v0/collisions/schemas.py` (moved `CollisionLogEntrySchema`), `api/v0/channels/schemas.py`, and the `ModelSettingsResponse` additions to `api/v0/system/schemas.py`;
  - 501 route stubs with final signatures and operation ids in `api/v0/actions/router.py`, `api/v0/collisions/router.py`, `api/v0/channels/router.py` and `api/v0/system/models.py`;
  - the registration in `api/v0/__init__.py`;
  - `since` accepted and ignored on `listLoops`.
- [x] T003 [P] [L:lead] DI and stubs, with tests:
  - **DI (A-2):** `ZeContainer` gains `action_record_store`, `user_channel_store` and `watermark_store` fields, from the instances `wiring/stores.py` already builds. `api/deps.py` gains `get_action_record_store`, `get_user_channel_store`, `get_watermark_store` and `get_channel_registry`; a test per getter resolves it from a built container.
  - **Reset sites:** remove `reset_service` from `wiring/container.py` (the import at ~77, the field at ~265 and the construction at ~670).
  - **Domain stubs: `ActionSubjectKind` and its context-key map in `ze_memory/action_records/types.py` (test: the map is closed, unknown kind raises a typed error); `list_by_subject` on the `ActionRecordStore` Protocol (signature only); `PollOutcome` and `ChannelPollStatus` in `ze_personal/channels/types.py`; `record_outcome` and `get_status_many` signatures on `ChannelWatermarkStore` raising `NotImplementedError`.**
- [x] T004 [L:lead] `make codegen`; commit `packages/ze-client/src/generated/*` with T002. Hand the route bodies and store bodies to their lanes (Handoffs note).

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - See what Ze did, by goal, workflow or run (P1) 🎯 MVP

- [x] T005 [L:ledger] [US1] Tests first `core/cognition/ze-memory/tests/action_records/test_list_by_subject.py` (mocked pool, asserting the SQL and params):
  - the subject clause uses the mapped key from the closed map (never interpolated from input), with `$n::text`;
  - `since` uses `occurred_at > $n::timestamptz`;
  - the cursor clause `(occurred_at, id) < ($a::timestamptz, $b::uuid)` appears only when a cursor is given (no cursor means no clause, K-1);
  - the order is `occurred_at DESC, id DESC`;
  - with no subject, every record is returned.

  Implement `list_by_subject` in `PostgresActionRecordStore`.
- [x] T005a [L:ledger] [US1] Tests first `core/automation/ze-automation/tests/test_action_records_workflow.py` (A-1): `finish_execution` runs `UPDATE … RETURNING workflow_id` and calls `emit_workflow_finished(execution_id, status, workflow_id)`; the emitted record's context has both `workflow_id` and `workflow_run_id`; a missing execution row (no row returned) still emits with `workflow_id=None` and logs. Implement in `ze_automation/workflow/postgres.py` (`finish_execution` only) and `ze_automation/action_records.py`.
- [x] T006 [L:ledger] [US1] `@pytest.mark.pg` test in the same package: seed records for goal G1, goal G2 and workflow run R1, plus one with an empty context. Listing by G1 returns only G1's records, newest first; listing by workflow W returns both its started and finished records. Paging with limit 1 walks all records with no repeat or skip, including two records with the same `occurred_at`. `since` excludes older records.
- [x] T007 [L:ledger] [US1] Tests first `apps/ze-api/tests/api/test_actions_route.py`:
  - each subject type maps to the store call;
  - a lone `subject_type` or `subject_id` → 422;
  - a bad cursor → 422;
  - a limit over 200 → 422;
  - an empty result → 200 with `items: []` and `next_cursor: null`;
  - `next_cursor` round-trips;
  - the item fields match the contract, including `touched`.
  
  Implement `api/v0/actions/router.py`.

---

## Phase 4: User Story 2 - See disagreements in Governance (P2)

- [x] T008 [L:reads] [US2] Move `apps/ze-api/tests/api/test_collisions_route.py` to target the product path and update `test_dev_only_routes.py` (collisions no longer dev-only) and `test_openapi_export.py`. Implement the handler body in `api/v0/collisions/router.py` (same filters; an unknown `source_function` → 422, not 500; `limit` 1..200 with 422 outside; `since > until` → empty list). Update `apps/ze-api/README.md` (~36: collisions under `api/v0`). Delete `api/eval/collisions.py`, its `include_router` line in `api/eval/__init__.py`, and `CollisionLogEntrySchema` from `api/eval/schemas.py`. A test asserts the old dev path returns 404 with the dev router mounted.

---

## Phase 5: User Story 3 - Print the configured model tier (P2)

- [x] T009 [L:reads] [US3] Tests first `apps/ze-api/tests/api/test_model_settings_route.py` (settings fixture copied from the real YAML into `tmp_path`):
  - the shipped config → `complexity_enabled: true`, `simple_max: 0.4`;
  - enabled with a null `simple_max` → `complexity_enabled: false` (it uses `ComplexitySurfaceConfig.calibrated`, T-1);
  - agents are sorted by name, each with `model` from `resolve_agent_model(name, "full", cfg)` and `model_simple` only when the agent declares one;
  - after the fixture's `system_one.surfaces.complexity.enabled` is set false and the settings are reloaded on the container → `false`;
  - no key containing `key`, `token` or `secret` appears in the JSON.
  
  Implement `api/v0/system/models.py`.

---

## Phase 6: User Story 4 - Closed loops by time (P2)

- [x] T010 [P] [L:reads] [US4] Tests first `core/cognition/ze-worldstate/tests/test_store_list_since.py` (mocked pool): `list(states=["closed", "dropped"], since=t)` adds `updated_at > $n` and the state set; `since=None` keeps the old SQL; existing callers (positional `states`) are unchanged. Implement in `PostgresLoopStore.list` and the `LoopStore` Protocol.
- [x] T011 [L:reads] [US4] `@pytest.mark.pg` test in the same package: loops closed 2, 5 and 20 days ago; `since` = 7 days ago returns the first two.
- [x] T012 [L:reads] [US4] Tests first `apps/ze-api/tests/api/test_loops_route.py` (extend): `state` is repeatable (`?state=closed&state=dropped` passes both); `since` is passed through and combines with it; an invalid datetime → 422. Implement in `api/v0/loops/router.py`.

---

## Phase 7: User Story 5 - Connection status in Governance (P3)

- [x] T013 [L:channels] [US5] Migration `plugins/ze-personal/ze_personal/migrations/versions/zc040_channel_poll_outcome.py` (revises `zc039`; the two nullable columns per [data-model.md](./data-model.md); downgrade drops them). Extend the migration chain test that T001 names in the Handoffs note (the test that asserts one head across `version_locations`) so `zc040` is on the single head.
- [x] T014 [L:channels] [US5] Tests first `plugins/ze-personal/tests/channels/test_watermark_outcome.py` (C-1):
  - `record_outcome` on an existing row UPDATEs the outcome columns and leaves `last_polled_at` unchanged;
  - with no row, it INSERTs `last_polled_at = now() - DEFAULT_LOOKBACK_HOURS` (never `now()`), so `get()` afterwards returns the lookback start;
  - `get_status_many` returns one `ChannelPollStatus` per id, with nulls for unknown ids.

  Add one `@pytest.mark.pg` test for the insert path with the FK satisfied. Implement in `watermark_store.py`.
- [x] T015 [L:channels] [US5] Tests first:
  - `integrations/ze-google/tests/test_auth_errors.py`: `is_auth_failure` is true for a `RefreshError` raised directly, as `__cause__`, or as `__context__` two levels down; false otherwise; it stops at depth 5.
  - `plugins/ze-messenger/tests/jobs/test_inbound_poll_outcome.py`:
    - a successful poll records `ok`;
    - an auth failure records `auth_failed`, after `ensure` (insert-if-absent) of the `user_channels` row first (call order asserted: a never-successful channel becomes listable); the failure path never calls `upsert`;
    - N-1: with an existing row (handle `me@x`) and an unresolved email, a failed poll leaves the handle `me@x`;
    - N-2: a failure with the email unresolved records under the bare key (`email`); a later success under `gmail:me@x` calls `drop_unkeyed("email")`; a success whose id equals the bare type value does not;
    - any other exception records `failed`;
    - push channels record nothing;
    - a failure while recording the outcome is logged and never breaks the poll;
    - the plugin does not import `google.auth` (a grep assertion).

  - `plugins/ze-personal/tests/channels/test_user_channel_store.py`: `ensure` inserts when absent and changes nothing when present; `drop_unkeyed` deletes the watermark row before the channel row, in one transaction, and is a no-op with no rows. One `@pytest.mark.pg` test: fail (bare key), re-auth, succeed → `list_all()` and `GET /channels/status` give one Gmail row, `connected`.

  Implement `ze_google/auth_errors.py` (exported from the package), `UserChannelStore.ensure` and `drop_unkeyed` in `ze_personal/channels/user_channel_store.py`, and `ze_messenger/jobs/inbound_poll.py`.
- [x] T016 [L:channels] [US5] Tests first `apps/ze-api/tests/api/test_channel_status_route.py`:
  - the state mapping: `poll_enabled` false → `off`; push → `unknown` with the line "Receives by push; Ze does not monitor it."; `auth_failed` → `needs_reauth`; `failed` → `error`; `ok` → `connected`; no outcome → `unknown`;
  - `last_sync_at` is the watermark only after an `ok` outcome, else null;
  - a registry inbound channel missing from `user_channels` is still listed;
  - no Google credentials → `google_configured: false`;
  - no token, secret or refresh field in the JSON.
  
  Implement `api/v0/channels/router.py`.

---

## Phase 8: User Story 6 - The broken reset is removed (P3)

- [x] T017 [L:jr1] [US6] Delete (the container's three reset sites are removed by `lead` in T003):
  - `core/ops/ze-onboarding/ze_onboarding/reset.py` and its names in `ze_onboarding/__init__.py`;
  - the `reset_service` assertions in `apps/ze-api/tests/api/test_ws_commands_reset_removed.py` (~38-39);
  - `scripts/reset_personal_state.py`;
  - the `reset-personal-state` target, its `.PHONY` entry and its help line in `Makefile`;
  - `apps/ze-api/tests/onboarding/test_reset.py`.

  Done when `git grep -niE "ResetService|reset_service|reset_personal_state|reset-personal|ResetScope|ResetPreview" -- . ':!specs' ':!docs'` returns nothing, and `make test-onboarding` and `make test` pass. (Docs are lane `docs`.)

---

## Phase 9: Polish and cross-cutting

- [x] T018 [P] [L:ledger] Follow-up note (no code): record in the Handoffs note that calendar, reminder and prospecting producers stamp no goal, workflow or run (spec US1 coverage limit), for a later instrumentation phase.
- [x] T019 [L:lead] Merge the lanes (ledger, reads, channels, jr1); `make codegen` if a schema moved; gates: `make test-py`, `make test-pg`, `make lint`, `make test-web`.
- [x] T020 [L:lead] Run [quickstart.md](./quickstart.md) steps 1–6 against `make dev`; record results in the Handoffs note.
- [x] T021 [P] [L:docs] `docs/native-interface.md` (five surfaces), `docs/memory.md` (ledger read), `docs/system-one.md` (tier settings route), `docs/architecture.md` (REST table; `zc040`), from the merged diff, doc-style skill.
- [x] T022 [P] [L:docs] `docs/onboarding.md` (the whole "Reset Scopes" section, ~164-181 → `make db-reset` / `make db-reset-seed`); any README/CONTRIBUTING mention found at T001; `AGENTS.md` phase row 194 and the ze-personal migration row (`user_channel_watermarks.last_outcome`, `zc040`); `specs/README.md` row 194 → Implemented; spec status.
- [x] T023 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002, T003 → T004 (contract) → lanes.
- ledger: T005 → T006, T007; T005a. reads: T008; T009; T010 → T011, T012. channels: T013 → T014 → T015, T016. jr1: T017.
- T019 after all lanes; T020 after T019; T021–T022 after T019; T023 last. T018 any time after T005.

## Parallel Example

```text
After the contract step, four lanes at once:
  ledger:   T005 → T006 → T007
  reads:    T008 | T009 | T010 → T011 → T012
  channels: T013 → T014 → T015 → T016
  jr1:      T017
```

## Implementation Strategy

- MVP = US1 (the ledger route Doing waits for). US2–US4 are small and independent; US5 carries the one migration; US6 is a deletion. Each story's route is usable alone after the contract step.

---

## Handoffs

**Contract step (lead, T001-T004)**
- Chain test for T013: `apps/ze-api/tests/test_migrate.py` (single head across `version_locations`; `zc039` lives in ze-core `migrations/versions`, so `zc040` goes in ze-personal with `down_revision = "zc039"`).
- Reset references outside specs: `Makefile`, `apps/ze-api/tests/onboarding/test_reset.py`, `ze_onboarding/{__init__,reset}.py`, `docs/onboarding.md`, `scripts/reset_personal_state.py`, plus `reset_service` assertions in `tests/api/test_ws_commands_reset_removed.py`. Matches plan.md; no README/CONTRIBUTING mention.
- Done early by lead (reads: do not redo): `/api/v0/collisions` removed from `EVAL_ONLY_PATHS` (`test_dev_only_routes.py`) and the "not in paths" assertion in `test_openapi_export.py`. Reads still owns the handler, the 404-on-old-path test and deleting `api/eval/collisions.py`.
- Stubs: product routes return 501; `PostgresActionRecordStore.list_by_subject`, `ChannelWatermarkStore.record_outcome` and `get_status_many` raise `NotImplementedError`. `subject_context_key()` and `UnknownActionSubjectKindError` are in ze-memory.
- Not done in T001: `graphify affected` and the ledger `EXPLAIN` (R2). Ledger lane runs the `EXPLAIN` with T005.

**Ledger lane (T005-T007, T018)**
- `list_by_subject` is built to the plan; `kind` and `subject_id` must come together (typed `StoreError` otherwise). The route fetches `limit + 1` rows to decide `next_cursor`.
- R2 EXPLAIN (empty throwaway DB): a Seq Scan with a top-N sort on `(occurred_at DESC, id DESC)`. The table is empty so the planner shows nothing about the index; at single-user volume (the plan's goal: 50 rows under 100 ms) no new index is added.
- Existing tests that mocked `conn.execute` for `finish_execution` now mock `conn.fetchrow` (it returns `workflow_id`).
- pg tests live in `apps/ze-api/tests/pg/test_action_records_subject_pg.py` (the harness is there). Run against a throwaway DB `ze_ledger_194` on ze-postgres-1; 4 passed.
- Coverage limit for a later instrumentation phase (T018): calendar, reminder and prospecting producers stamp no goal, workflow or run id in their action context, so what Ze did through those tools during a goal or workflow does not list under that subject.

**T020 quickstart (lead, throwaway DB ze_e2e_194, port 8030, EVAL_MODE, seeded; dropped after)**
- 1 actions: goal subject lists only that goal, newest first; `next_cursor` followed to the second record, then null; lone `subject_type` 422; bad cursor 422.
- 2 collisions: `/api/v0/collisions` 200 (`[]`, none seeded); unknown `source_function` 422; `/eval/collisions` 404.
- 3 system/models: `complexity_enabled: true`, `simple_max: 0.4`, agents sorted. The config-off + SIGHUP flip is covered by the route test, not run live.
- 4 loops: repeated `state` and `since` return 200; the seed has no closed loops, so the filtering itself is covered by the unit and pg tests only.
- 5 channels/status: `google_configured: true`, one registry channel `email` / `unknown`. A revoked live Google token was not exercised (no real Google calls); the outcome path is covered by the job tests and the store-level pg test.
- 6 `make reset-personal-state`: no rule; `db-reset-seed` target present.
- **Bug found and fixed (outside any lane):** `PostgresActionRecordStore.append` passed `json.dumps` strings to jsonb columns on a pool that already encodes with `json.dumps`, so production rows held a jsonb string and `context->>'goal_id'` matched nothing (the lane pg tests inserted raw SQL on a codec-less pool, so they passed). Fixed to pass objects, plus a pg test appending through the production codec pool. The seed fixture `ze_seed/domains/automation.py` had the same bug for its two action records; fixed. Other `json.dumps` seed calls and other stores may have the same pattern; not audited.

**T023 docs coverage (lead did the docs lanes)**: `git diff 7ca568ba --stat` touches AGENTS.md, apps/ze-api/README.md (reads), docs/{architecture,memory,native-interface,onboarding,system-one}.md and specs/README.md, spec status; this matches plan.md "Docs touched". T001 left no README/CONTRIBUTING reset mention. `docs/onboarding.md` "Reset Scopes" is now "Resetting a dev database".
