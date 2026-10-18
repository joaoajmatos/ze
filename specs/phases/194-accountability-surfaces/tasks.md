# Tasks: Accountability Surfaces (B4)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/rest.md](./contracts/rest.md), [quickstart.md](./quickstart.md).

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests mock asyncpg; the two SQL filters also get one `@pytest.mark.pg` test each.

**Build gate**: starts now on `main`; runs in parallel with the web floors. `zc040` must be reserved with the Maestro before T013 (the `zc` chain is shared; head is `zc039`).

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:ledger]`, `[L:reads]`, `[L:channels]`, `[L:jr1]`, `[L:docs]` (plan.md Lane Plan). A task touches only files its lane owns.
- **[Story]**: US1 actions, US2 collisions, US3 tier settings, US4 loops since, US5 channel status, US6 reset deletion.

**Crew**: Sonnet `lead`, `ledger`, `reads`, `channels`; Haiku `jr1` (the fully specified deletion) and `docs`. Contract step first; then the lanes run in parallel in their own worktrees; `lead` merges ledger → reads → channels → jr1. Tick a task's checkbox in the same commit that finishes it.

**Rules for every lane**: `graphify affected` and `rtk proxy grep` before changing a shared symbol; typed `ZeError`s; `get_logger(__name__)`; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [ ] T001 [L:lead] Branch from `main`. `make install`; `graphify update .`; `graphify affected` on `ActionRecordStore`, `LoopStore`, `ChannelWatermarkStore`, `InboundPollingJob`, `ResetService`, `list_collisions`, `complexity_surface_config`, `resolve_agent_model`. Grep `reset_personal_state\|reset-personal-state\|ResetService` across the repo (docs, CONTRIBUTING, README, Makefile). Run `EXPLAIN` for the planned ledger query on the dev DB (research R2). Ask the Maestro to reserve `zc040`. Name the migration chain test file (the one asserting a single head) for T013. Record differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first `apps/ze-api/tests/api/test_accountability_contract.py`: the OpenAPI export lists `listActionRecords`, `listCollisions` (product spec, not the dev spec), `getModelSettings`, `listChannelStatus`, and `listLoops` with a `since` parameter, each with its response model from [contracts/rest.md](./contracts/rest.md). Implement:
  - the schemas: `api/v0/actions/schemas.py`, `api/v0/collisions/schemas.py` (moved `CollisionLogEntrySchema`), `api/v0/channels/schemas.py`, and the `ModelSettingsResponse` additions to `api/v0/system/schemas.py`;
  - 501 route stubs with final signatures and operation ids in `api/v0/actions/router.py`, `api/v0/collisions/router.py`, `api/v0/channels/router.py` and `api/v0/system/models.py`;
  - the registration in `api/v0/__init__.py`;
  - `since` accepted and ignored on `listLoops`.
- [ ] T003 [P] [L:lead] Domain stubs with tests: `ActionSubjectKind` and its context-key map in `ze_memory/action_records/types.py` (test: the map is closed, unknown kind raises a typed error); `list_by_subject` on the `ActionRecordStore` Protocol (signature only); `PollOutcome` and `ChannelPollStatus` in `ze_personal/channels/types.py`; `record_outcome` and `get_status_many` signatures on `ChannelWatermarkStore` raising `NotImplementedError`.
- [ ] T004 [L:lead] `make codegen`; commit `packages/ze-client/src/generated/*` with T002. Hand the route bodies and store bodies to their lanes (Handoffs note).

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - See what Ze did, by goal, workflow or run (P1) 🎯 MVP

- [ ] T005 [L:ledger] [US1] Tests first `core/cognition/ze-memory/tests/action_records/test_list_by_subject.py` (mocked pool, asserting SQL and params): the subject filter uses the mapped context key, passed as a parameter and never interpolated from input; `since` filters `occurred_at >`; the cursor applies `(occurred_at, id) <`; the order is `occurred_at DESC, id DESC`; `limit` is passed. With no subject, every record is returned. Implement `list_by_subject` in `PostgresActionRecordStore`.
- [ ] T006 [L:ledger] [US1] `@pytest.mark.pg` test in the same package: seed records for goal G1, goal G2 and workflow run R1, plus one with an empty context. Listing by G1 returns only G1's records, newest first. Paging with limit 1 walks all records with no repeat or skip, including two records with the same `occurred_at`. `since` excludes older records.
- [ ] T007 [L:ledger] [US1] Tests first `apps/ze-api/tests/api/test_actions_route.py`:
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

- [ ] T008 [L:reads] [US2] Move `apps/ze-api/tests/api/test_collisions_route.py` to target the product path and update `test_dev_only_routes.py` (collisions no longer dev-only) and `test_openapi_export.py`. Implement the handler body in `api/v0/collisions/router.py` (same filters, `limit ≤ 200`, `since > until` → empty list). Delete `api/eval/collisions.py`, its `include_router` line in `api/eval/__init__.py`, and `CollisionLogEntrySchema` from `api/eval/schemas.py`. A test asserts the old dev path returns 404 with the dev router mounted.

---

## Phase 5: User Story 3 - Print the configured model tier (P2)

- [ ] T009 [L:reads] [US3] Tests first `apps/ze-api/tests/api/test_model_settings_route.py` (settings fixture copied from the real YAML into `tmp_path`):
  - the shipped config → `complexity_enabled: true`, `simple_max: 0.4`;
  - agents are sorted by name, each with `model` from `resolve_agent_model(name, "full", cfg)` and `model_simple` only when the agent declares one;
  - after the fixture's `system_one.surfaces.complexity.enabled` is set false and the settings are reloaded on the container → `false`;
  - no key containing `key`, `token` or `secret` appears in the JSON.
  
  Implement `api/v0/system/models.py`.

---

## Phase 6: User Story 4 - Closed loops by time (P2)

- [ ] T010 [P] [L:reads] [US4] Tests first `core/cognition/ze-worldstate/tests/test_store_list_since.py` (mocked pool): `list(states=["closed"], since=t)` adds `updated_at > $n`; `since=None` keeps the old SQL; existing callers (positional `states`) are unchanged. Implement in `PostgresLoopStore.list` and the `LoopStore` Protocol.
- [ ] T011 [L:reads] [US4] `@pytest.mark.pg` test in the same package: loops closed 2, 5 and 20 days ago; `since` = 7 days ago returns the first two.
- [ ] T012 [L:reads] [US4] Tests first `apps/ze-api/tests/api/test_loops_route.py` (extend): `since` is passed through and combines with `state`; an invalid datetime → 422. Implement in `api/v0/loops/router.py`.

---

## Phase 7: User Story 5 - Connection status in Governance (P3)

- [ ] T013 [L:channels] [US5] Migration `plugins/ze-personal/ze_personal/migrations/versions/zc040_channel_poll_outcome.py` (revises `zc039`; the two nullable columns per [data-model.md](./data-model.md); downgrade drops them). Extend the migration chain test that T001 names in the Handoffs note (the test that asserts one head across `version_locations`) so `zc040` is on the single head.
- [ ] T014 [L:channels] [US5] Tests first `plugins/ze-personal/tests/channels/test_watermark_outcome.py`: `record_outcome` upserts `last_outcome`/`last_outcome_at` without changing the watermark (and creates the row with a null watermark if absent); `get_status_many` returns one `ChannelPollStatus` per id, with nulls for unknown ids. Implement in `watermark_store.py`.
- [ ] T015 [L:channels] [US5] Tests first `plugins/ze-messenger/tests/jobs/test_inbound_poll_outcome.py`:
  - a successful poll records `ok`;
  - a `google.auth.exceptions.RefreshError`, raised directly or as the `__cause__` of another error, records `auth_failed`;
  - any other exception records `failed`;
  - push channels record nothing;
  - a failure while recording the outcome is logged and never breaks the poll.
  
  Implement in `ze_messenger/jobs/inbound_poll.py`.
- [ ] T016 [L:channels] [US5] Tests first `apps/ze-api/tests/api/test_channel_status_route.py`:
  - the state mapping (`poll_enabled` false → `off`; `auth_failed` → `needs_reauth`; `failed` → `error`; otherwise `connected`);
  - `last_sync_at` is the watermark;
  - a push channel → `push: true`, `last_sync_at` null;
  - no Google credentials → `google_configured: false`;
  - no token, secret or refresh field in the JSON.
  
  Implement `api/v0/channels/router.py`.

---

## Phase 8: User Story 6 - The broken reset is removed (P3)

- [ ] T017 [L:jr1] [US6] Delete:
  - `core/ops/ze-onboarding/ze_onboarding/reset.py`, its names in `ze_onboarding/__init__.py`, and the reset-service lines in `apps/ze-api/ze_api/wiring/container.py`;
  - `scripts/reset_personal_state.py`;
  - the `reset-personal-state` target, its `.PHONY` entry and its help line in `Makefile`;
  - `apps/ze-api/tests/onboarding/test_reset.py`.

  Done when `rtk proxy grep -rn "ResetService\|reset_personal_state\|reset-personal-state\|ResetScope\|ResetPreview" core apps plugins scripts Makefile` returns nothing, and `make test-onboarding` and `make test` pass. (Docs are lane `docs`.)

---

## Phase 9: Polish and cross-cutting

- [ ] T018 [P] [L:ledger] Follow-up note (no code): if T001 or T005 found producers that stamp only `workflow_run_id` while the workflow id is at hand (research R1), write one line for the next ze-automation phase in the Handoffs note.
- [ ] T019 [L:lead] Merge the lanes (ledger, reads, channels, jr1); `make codegen` if a schema moved; gates: `make test-py`, `make test-pg`, `make lint`, `make test-web`.
- [ ] T020 [L:lead] Run [quickstart.md](./quickstart.md) steps 1–6 against `make dev`; record results in the Handoffs note.
- [ ] T021 [P] [L:docs] `docs/native-interface.md` (five surfaces), `docs/memory.md` (ledger read), `docs/system-one.md` (tier settings route), `docs/architecture.md` (REST table; `zc040`), from the merged diff, doc-style skill.
- [ ] T022 [P] [L:docs] `docs/onboarding.md` (the reset paragraph → `make db-reset` / `make db-reset-seed`); any README/CONTRIBUTING mention found at T001; `AGENTS.md` phase row 194 and the ze-personal migration row (`user_channel_watermarks.last_outcome`, `zc040`); `specs/README.md` row 194 → Implemented; spec status.
- [ ] T023 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002, T003 → T004 (contract) → lanes.
- ledger: T005 → T006, T007. reads: T008; T009; T010 → T011, T012. channels: T013 → T014 → T015, T016. jr1: T017.
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
