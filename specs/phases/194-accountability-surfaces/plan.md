# Implementation Plan: Accountability Surfaces (B4)

**Branch**: `194-accountability-surfaces` | **Date**: 2026-10-18 (revised after Gauge's review A-1, A-2, C-1..C-3, R-1, T-1, Co-1, L-1, K-1) | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended), `main` at ab334b60. `zc040` reserved for this phase by the Maestro.

## Summary

Five read surfaces and one deletion:

1. **Action records.** A ledger read by subject in ze-memory, and `GET /api/v0/actions` (`listActionRecords`) with keyset paging. The workflow-finished record now carries its workflow id (A-1), so a workflow's list shows each run's outcome.
2. **Collisions.** `GET /api/v0/collisions` moves to the product router, with bad input returning 422.
3. **Tier settings.** `GET /api/v0/system/models` (`getModelSettings`) reports `complexity_enabled` as `ComplexitySurfaceConfig.calibrated`.
4. **Loops `since`.** `listLoops` accepts repeated `state` values and a `since` on `updated_at`.
5. **Channel status.** `GET /api/v0/channels/status` (`listChannelStatus`). Poll outcomes are recorded on the watermark row (`zc040`) without moving the watermark. A channel that never worked is registered on its first failure, and push channels report `unknown`.
6. **Reset deletion.** `ResetService`, its script, its make target and its tests are removed.

## Technical Context

**Language/Version**: Python 3.12.
**Primary Dependencies**: existing. ze-google gains `is_auth_failure(exc) -> bool`, which hides `google.auth.exceptions.RefreshError` from the messenger plugin.
**Storage**: `zc040_channel_poll_outcome` (ze-personal, revises `zc039`) adds `last_outcome TEXT NULL` and `last_outcome_at TIMESTAMPTZ NULL` to `user_channel_watermarks`.
**Testing**: pytest with mocked pools; `@pytest.mark.pg` for the ledger subject filter, the loops filter and the watermark outcome upsert.
**Target Platform / Project Type**: Linux container; web service (backend; regenerated client).
**Performance Goals**: action list of 50 rows in under 100 ms at single-user volume (no index needed: the `occurred_at DESC` index exists).
**Constraints**: no secrets in responses; keyset paging on `(occurred_at, id)`; poll outcomes never move `last_polled_at`.
**Scale/Scope**: single user.

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec, clarifications, plan, research, data model, contracts, quickstart, tasks, checklist. |
| II Single-user | no scoping added. |
| III Layered packages | Ledger read in ze-memory. The workflow id is stamped in ze-automation, the record's producer. Loops in ze-worldstate. Watermark outcome in ze-personal, written by ze-messenger (declared edge). The auth-failure check is in ze-google, which ze-messenger already depends on, so the plugin never imports `google.auth`. Routes and DI live in ze-api. |
| IV Typed Python | `ActionSubjectKind`, `PollOutcome`, `ChannelPollStatus`; typed errors; 422s for bad input. |
| V Tests | fail-first; pg tests for the three SQL changes. |
| VI Persistence | `zc040` in ze-personal's `zc` chain. |
| VIII Hard cuts | eval collisions route and `ResetService` deleted; manifest unchanged. |

Gate: pass.

## Blast radius

| Symbol | Callers | Change |
|---|---|---|
| `ActionRecordStore.list` | procedure store, tests | unchanged; `list_by_subject` added |
| `emit_workflow_finished(execution_id, status)` (`ze_automation/action_records.py:75`) | `PostgresWorkflowStore.finish_execution` (`workflow/postgres.py:435`) | gains `workflow_id`; `finish_execution` uses `UPDATE … RETURNING workflow_id` and passes it (A-1) |
| `api/eval/collisions.py` | `api/eval/__init__.py:3,10`, `tests/api/test_collisions_route.py`, `test_dev_only_routes.py`, `test_openapi_export.py`, `apps/ze-api/README.md:36` | moved to `api/v0/collisions/`; the README is updated |
| `LoopStore.list(states)` | loops router, surfacers, priority, recap | gains `since` (keyword) |
| `list_loops` | web `useLoopsQuery`, World Touched (`useWorld.ts:66`, `state=closed`) | `state` becomes repeatable; `since` added. Web adoption (closed and dropped in one call) is a later web change. |
| `ChannelWatermarkStore` | inbound poll job | gains `record_outcome`, `get_status_many` |
| `InboundPollingJob._poll` | scheduler | records outcomes; registers the channel on first failure |
| `ZeContainer` (`ze_api/wiring/container.py`) | routes, endpoint | gains `action_record_store`, `user_channel_store`, `watermark_store` fields (today only in `wiring/stores.py` and the agent DI map, `wiring/agents.py:93-94`); loses `reset_service` (import line 77, field 265, construction 670) |
| `ze_api/api/deps.py` | routes | adds `get_action_record_store`, `get_user_channel_store`, `get_watermark_store`, `get_channel_registry` |
| `complexity_surface_config` (`.calibrated`), `resolve_agent_model` | `choose_tier` | read by the settings route |
| `ResetService` | `ze_onboarding/{reset.py,__init__.py}`, container (three sites), `scripts/reset_personal_state.py`, Makefile (target, `.PHONY` line 153, help line), `apps/ze-api/tests/onboarding/test_reset.py`, `apps/ze-api/tests/api/test_ws_commands_reset_removed.py:38-39` (asserts on `container.reset_service`), `docs/onboarding.md:164-181` (the "Reset Scopes" section) | all deleted or edited |
| Phase 192 | adds `transcription_registry` to `wiring/container.py` | merge order: the second floor to land rebases that file |

## Design

### Action records

- **ze-memory `types.py`:** `ActionSubjectKind` and a closed map to the context keys `goal_id`, `workflow_id`, `workflow_run_id` and `workspace_run_id`.
- **ze-memory `store.py`:** `list_by_subject(*, kind=None, subject_id=None, since=None, cursor=None, limit=50)`. The SQL is assembled from fixed fragments:
  - `context->>'<mapped key>' = $n::text` when a subject is given (the key comes from the closed map, never from input);
  - `occurred_at > $n::timestamptz` when `since` is given;
  - `(occurred_at, id) < ($a::timestamptz, $b::uuid)` only when a cursor is present (K-1);
  - then `ORDER BY occurred_at DESC, id DESC LIMIT $n`.
- **ze-automation (A-1):** `finish_execution` runs `UPDATE workflow_executions … RETURNING workflow_id`. `emit_workflow_finished(execution_id, status, workflow_id)` stamps `ActionContext(workflow_id=…, workflow_run_id=…)`.
- **Coverage limit (spec US1, assumptions).** Goal-trace, workflow and workspace records carry their subject. Calendar, reminder and prospecting records carry only their own keys, so what Ze did through those tools during a goal or workflow does not list under that subject.
- **ze-api `api/v0/actions/`:** `GET /actions`. `subject_type` and `subject_id` must be given together, else 422. `since`; `cursor` (base64 of `occurred_at|id`, 422 if invalid); `limit` 1..200, default 50. Returns `ActionRecordPage`.

### Collisions

- `api/v0/collisions/router.py`: the same filters on the product router. An unknown `source_function` returns 422 (no `ValueError` escapes), and `limit` is 1..200. `api/eval/collisions.py` is deleted along with its include line and its schema in `api/eval/schemas.py`. `apps/ze-api/README.md` is updated.

### Tier settings

- `api/v0/system/models.py`: `GET /system/models`. `complexity_enabled` is `complexity_surface_config(settings).calibrated` (enabled and a bar, T-1), and `simple_max` is the bar or null. Agents are sorted by name, with `model` and `model_simple` from `resolve_agent_model`. No secrets.

### Loops

- `PostgresLoopStore.list(states=None, *, since=None)` adds `AND updated_at > $n` (every transition sets `updated_at`).
- The `listLoops` route takes `state: list[str] | None = Query(None)` (repeatable) and `since`. One call returns closed and dropped loops (L-1).

### Channel status

- **Migration `zc040`:** the two nullable columns.
- **`ChannelWatermarkStore.record_outcome(channel_id, outcome, at)`** (C-1):
  - `UPDATE user_channel_watermarks SET last_outcome, last_outcome_at WHERE channel_id = $1`.
  - If no row is updated, `INSERT … (channel_id, last_polled_at, last_outcome, last_outcome_at) VALUES ($1, now() - DEFAULT_LOOKBACK, …)`, so the next successful poll starts from the normal 24 h lookback and no mail in the failure window is skipped.
  - The watermark is never moved forward by an outcome.
- **`get_status_many(ids)`** returns `ChannelPollStatus` per id.
- **ze-google:** `is_auth_failure(exc)` walks `__cause__` and `__context__` up to depth 5, looking for `google.auth.exceptions.RefreshError`.
- **`InboundPollingJob._poll`:**
  - **Success:** the existing watermark set and `user_channels` upsert, then `record_outcome(ok)`.
  - **Exception:** first the same `user_channels` upsert the success path does (so the FK holds and `list_all()` includes the channel), then `record_outcome(auth_failed if is_auth_failure(exc) else failed)`.
  - **Partial failures:** per-message `get` failures inside `poll_new_messages` are swallowed by the channel and still count as `ok` (stated in the spec).
  - **Outcome-recording failures** are logged and never break the poll.
- **ze-api `api/v0/channels/`:** `GET /channels/status`. Channels come from `UserChannelStore.list_all()` merged with the `ChannelRegistry` inbound channels. A registry channel that is not yet in `user_channels` is listed with no handle and `unknown` if it never polled. States:
  - `off` when `poll_enabled` is false;
  - `unknown` for push channels (C-2: "Receives by push; Ze does not monitor it."). Gmail with `PUBLIC_URL` set is the usual deployment;
  - `needs_reauth` for `auth_failed`;
  - `error` for `failed`;
  - `connected` for `ok`;
  - `unknown` when there is no outcome yet.
  
  Fields: `last_sync_at` (the watermark row's `last_polled_at` when the row exists and the last outcome was `ok`, else null), `push`, `google_configured`. No tokens.

### DI (lead, contract step)

- `ZeContainer` gains `action_record_store`, `user_channel_store` and `watermark_store` fields, from the instances `wiring/stores.py` already builds. `api/deps.py` gains `get_action_record_store`, `get_user_channel_store`, `get_watermark_store` and `get_channel_registry`, each with a resolve test.

### Reset deletion

- `jr1` deletes the files and lines outside the container. `lead` removes the three container sites, because `lead` owns `container.py`.

## Project Structure

### Documentation (this feature)

```text
specs/phases/194-accountability-surfaces/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/rest.md
└── checklists/{requirements.md,api.md}
```

### Source Code

```text
core/cognition/ze-memory/ze_memory/action_records/{types.py,store.py}
core/automation/ze-automation/ze_automation/{action_records.py,workflow/postgres.py}
core/cognition/ze-worldstate/ze_worldstate/store.py
integrations/ze-google/ze_google/auth_errors.py (new: is_auth_failure)
plugins/ze-personal/ze_personal/channels/{watermark_store.py,types.py} ; .../migrations/versions/zc040_channel_poll_outcome.py
plugins/ze-messenger/ze_messenger/jobs/inbound_poll.py
apps/ze-api/ze_api/api/v0/{actions,collisions,channels}/ (new) ; api/v0/system/models.py (new)
apps/ze-api/ze_api/api/{deps.py,v0/__init__.py,v0/loops/router.py,eval/__init__.py,eval/collisions.py (deleted),eval/schemas.py}
apps/ze-api/ze_api/wiring/container.py ; apps/ze-api/README.md
core/ops/ze-onboarding/ze_onboarding/{reset.py (deleted),__init__.py} ; scripts/reset_personal_state.py (deleted) ; Makefile
packages/ze-client/src/generated/*
```

## Docs touched

- `docs/native-interface.md`: the five surfaces.
- `docs/memory.md`: ledger read by subject and which producers carry a subject.
- `docs/system-one.md`: the tier settings route.
- `docs/onboarding.md` (lines ~164-181): the "Reset Scopes" section replaced by `make db-reset` / `make db-reset-seed`.
- `docs/architecture.md`: REST table; migration table row for `zc040`.
- `apps/ze-api/README.md` (~36): collisions under `api/v0`.
- `AGENTS.md`: phase row 194; migration ownership (ze-personal `user_channel_watermarks.last_outcome`, `zc040`); `specs/README.md` row 194.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004):
- **Pydantic schemas** for the five surfaces, plus 501 route stubs with final operation ids, registered.
- **Domain type stubs** and Protocol signatures.
- **Container fields** and `deps.py` getters with resolve tests.
- **Container reset sites** removed.
- `make codegen`.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `api/v0/__init__.py`, `api/deps.py`, `wiring/container.py`, all new `schemas.py`, domain type stubs, `packages/ze-client/src/generated/*`; merges and gates | T001–T004, T019, T020 | - | Gauge |
| ledger | Sonnet ENG | `ze_memory/action_records/store.py`, `ze_automation/action_records.py`, `ze_automation/workflow/postgres.py` (`finish_execution` only), `api/v0/actions/router.py`, their tests | T005, T005a, T006, T007, T018 | contract step | floor Reviewer |
| reads | Sonnet ENG | `api/v0/collisions/router.py`, `api/eval/{__init__,collisions,schemas}.py`, `apps/ze-api/README.md`, `api/v0/system/models.py`, `ze_worldstate/store.py`, `api/v0/loops/router.py`, their tests | T008–T012 | contract step | floor Reviewer |
| channels | Sonnet ENG | `zc040`, `ze_personal/channels/watermark_store.py`, `ze_google/auth_errors.py`, `ze_messenger/jobs/inbound_poll.py`, `api/v0/channels/router.py`, their tests | T013–T016 | contract step | floor Reviewer |
| jr1 | Haiku JR | `ze_onboarding/reset.py`, `ze_onboarding/__init__.py`, `scripts/reset_personal_state.py`, `Makefile` (target, `.PHONY`, help), `apps/ze-api/tests/onboarding/test_reset.py`, `apps/ze-api/tests/api/test_ws_commands_reset_removed.py` (the `reset_service` assertions) | T017 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" except `apps/ze-api/README.md` (lane `reads`) | T021–T023 | lanes merged | floor Reviewer |

**Rules**: one lane per file. `lead` merges ledger, reads, channels and jr1, then re-runs codegen and the gates. If phase 192 lands first, `lead` rebases `wiring/container.py` onto its `transcription_registry` line.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| `zc040` | "Needs re-auth" cannot be read from anything stored. | A stale-sync heuristic; an in-memory flag. |
| Push channels report `unknown` | Ze does not see failures on the push path (the webhook swallows errors, watches lapse), so "connected" would be a false green. | Recording webhook and renewal outcomes (needs a callback from ze-google into ze-personal; left for a messaging phase). |
