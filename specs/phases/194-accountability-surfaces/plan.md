# Implementation Plan: Accountability Surfaces (B4)

**Branch**: `194-accountability-surfaces` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended), `main` at ab334b60.

## Summary

Five read surfaces and one deletion, all over data that already exists:

1. **Action records.** A ledger read by subject in ze-memory, and `GET /api/v0/actions` (`listActionRecords`) with keyset paging.
2. **Collisions.** `GET /api/v0/collisions` moves from the dev/eval router to the product router; the eval copy is deleted.
3. **Tier settings.** `GET /api/v0/system/models` (`getModelSettings`) reads the same `complexity_surface_config` and `resolve_agent_model` that `choose_tier` uses.
4. **Loops `since`.** A `since` filter on `listLoops`, on the loop's last change.
5. **Channel status.** `GET /api/v0/channels/status` (`listChannelStatus`): each user channel's state and last sync. "Needs re-auth" requires recording the last poll outcome, which is only logged today, so the watermark row gains `last_outcome` and `last_outcome_at` (migration `zc040`, ze-personal) and the inbound poll job writes them.
6. **Reset deletion.** `ResetService`, `scripts/reset_personal_state.py` and `make reset-personal-state` are removed, with their tests and doc lines.

## Technical Context

**Language/Version**: Python 3.12.
**Primary Dependencies**: existing only (asyncpg, FastAPI, google-auth for the `RefreshError` class).
**Storage**: one migration, `zc040_channel_poll_outcome` in ze-personal: `ALTER TABLE user_channel_watermarks ADD COLUMN last_outcome TEXT NULL, ADD COLUMN last_outcome_at TIMESTAMPTZ NULL`. Values are `ok`, `auth_failed` and `failed`. `zc039` is the current `zc` head (195); `zc040` must be reserved with the Maestro, since the `zc` chain is shared.
**Testing**: pytest, `AsyncMock` pools; one `@pytest.mark.pg` test for the ledger subject filter (JSON context query) and one for the loops `since` filter.
**Target Platform**: Linux container, macOS dev.
**Project Type**: web service (backend; regenerated client only).
**Performance Goals**: the action list returns 50 rows in under 100 ms with an index on the subject keys (see research R2).
**Constraints**: no secrets in responses; keyset paging stable on `(occurred_at, id)`.
**Scale/Scope**: single user; the ledger grows by tens of rows a day.

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec + clarifications; plan, research, data model, contracts, quickstart, tasks. |
| II Single-user | no scoping added. |
| III Layered packages | Ledger read in ze-memory (owner of `action_records`). Loops filter in ze-worldstate. Channel outcome in ze-personal (owner of `user_channel_watermarks`), written by ze-messenger through its existing `ChannelWatermarkStore` dependency (ze-messenger → ze-personal is a declared edge). Routes only in ze-api. Tier settings read ze-core's `tier.py` from ze-api, which is allowed. |
| IV Typed Python | `ActionSubject`, `ChannelStatus`, `PollOutcome` dataclasses and enums; route errors typed. |
| V Tests | Fail-first; pg-marked tests for the two SQL filters. |
| VI Persistence | `zc040` raw SQL in ze-personal's chain, with `depends_on` none (it continues `zc039`). |
| VII Gateway | no LLM. |
| VIII Hard cuts | eval collisions route and `ResetService` deleted, no copy kept. |

Gate: pass.

## Blast radius

`graphify affected` (after `graphify update .`) plus grep:

| Symbol | Callers | Change |
|---|---|---|
| `ActionRecordStore.list` (`ze_memory/action_records/store.py:40`) | procedure store, recorder tests | unchanged; new `list_by_subject` beside it on the Protocol and `PostgresActionRecordStore` |
| `api/eval/collisions.py` `list_collisions` | `api/eval/__init__.py` (dev router), `tests/api/test_collisions_route.py`, `test_dev_only_routes.py`, `test_openapi_export.py` | moves to `api/v0/collisions/`; the dev router drops it; tests updated (the dev-only test no longer lists collisions; the export test expects `listCollisions` on the product spec) |
| `CollisionLogEntrySchema` (`api/eval/schemas.py`) | eval collisions route | moves to `api/v0/collisions/schemas.py` |
| `LoopStore.list(states)` (`ze_worldstate/store.py:98,199`) | loops router, surfacers, priority view, recap | gains `since: datetime | None = None` (keyword, default keeps every caller) |
| `list_loops` (`api/v0/loops/router.py:26`) | web `useLoopsQuery` | gains `since` query |
| `ChannelWatermarkStore` (`ze_personal/channels/watermark_store.py`) | inbound poll job, webhook path | gains `record_outcome(channel_id, outcome, at)` and `get_status_many(ids)` |
| `InboundPollingJob._poll` (`ze_messenger/jobs/inbound_poll.py`) | proactive scheduler | records `ok` / `auth_failed` / `failed` |
| `complexity_surface_config`, `resolve_agent_model` (`ze_core/routing/tier.py`) | `choose_tier` | read by the new settings route (no change) |
| `ResetService` (`ze_onboarding/reset.py`) | `ze_onboarding/__init__.py` export, `ze_api/wiring/container.py`, `scripts/reset_personal_state.py`, `Makefile` (`reset-personal-state`, help line), `apps/ze-api/tests/onboarding/test_reset.py`, `docs/onboarding.md` | all deleted or lines removed |

## Design

### Action records (ze-memory + ze-api)

- `ze_memory/action_records/types.py`: `ActionSubjectKind = Literal["goal", "workflow", "workflow_run", "workspace_run"]` mapped to context keys `goal_id`, `workflow_id`, `workflow_run_id`, `workspace_run_id`.
- `store.py`: `list_by_subject(*, kind: ActionSubjectKind | None, subject_id: UUID | None, since: datetime | None, cursor: tuple[datetime, UUID] | None, limit: int) -> list[ActionRecord]`. SQL: `WHERE ($kind IS NULL OR context->>$key = $id::text) AND ($since IS NULL OR occurred_at > $since) AND (occurred_at, id) < ($c_at, $c_id) ORDER BY occurred_at DESC, id DESC LIMIT $n`. Key names come from a closed map, never interpolated from input. The workflow subject also matches records whose context has only `workflow_run_id`, when that run belongs to the workflow: research R1 decides on context-only matching.
- Index: research R2 (an expression index in a `zm025` migration, only if T001 measures a need; default: none, given the single-user volume).
- ze-api `api/v0/actions/`: `GET /actions` with `subject_type`, `subject_id` (both or neither, else 422), `since`, `cursor` (opaque base64 of `occurred_at|id`), `limit` (1..200, default 50). Response `ActionRecordPage { items: [ActionRecordItem], next_cursor }`. Each item has id, action_type, actor, producer_plugin, lifecycle, outcome, summary, `touched {domain, record_id}`, occurred_at and failure_code.

### Collisions (ze-api)

- `api/v0/collisions/router.py` and `schemas.py`: the same handler, filters and schema, `operation_id="listCollisions"`, on the product router with `require_api_key`. `api/eval/collisions.py` and its `dev_router.include_router` line are deleted.

### Tier settings (ze-api)

- `api/v0/system/models.py` (new router file in the system package): `GET /system/models`, `operation_id="getModelSettings"`. It reads `container.settings` on each request (hot reload) and returns `{complexity_enabled, simple_max, agents: [{name, model, model_simple}]}`. `model` is `resolve_agent_model(name, "full", app_config)`; `model_simple` is `resolve_agent_model(name, "simple", app_config)` when the agent declares `model_simple`, else null. Agents come from the registry, sorted by name. No API keys or base URLs are included.

### Loops since (ze-worldstate + ze-api)

- `PostgresLoopStore.list(states=None, *, since=None)` adds `AND updated_at > $since` (`updated_at` moves on every transition: verify at T001 that `close`/`drop`/`transition` set it; if one does not, that statement gains `updated_at = now()`). The `listLoops` route gains a `since: datetime | None` query.

### Channel status (ze-personal + ze-messenger + ze-api)

- `zc040_channel_poll_outcome.py` (ze-personal `migrations/versions/`): the two columns, nullable.
- `ChannelWatermarkStore.record_outcome(channel_id, outcome: PollOutcome, at)` upserts the outcome columns without moving the watermark. `get_status_many(ids) -> dict[str, ChannelPollStatus(watermark, last_outcome, last_outcome_at)]`.
- `InboundPollingJob._poll`: on success, records `ok` (beside the existing watermark set). On exception, records `auth_failed` when the exception is (or wraps) `google.auth.exceptions.RefreshError`, else `failed`. Push channels (Gmail via webhook) are skipped by the poll job and never move a watermark today, so their status reads "connected" with `last_sync_at` null and `push: true`. Recording webhook outcomes is out of scope.
- ze-api `api/v0/channels/`: `GET /channels/status`, `operation_id="listChannelStatus"`. It reads `UserChannelStore.list_all()` and `get_status_many()`, and maps each channel to one of:
  - `off` when `poll_enabled` is false;
  - `needs_reauth` when `last_outcome == auth_failed`;
  - `error` when `failed`;
  - `connected` otherwise.

  Each item carries `last_sync_at` (the watermark), `channel_type`, `handle` and `display_name`. If Google credentials are not configured at all, the response carries `google_configured: false` and the list is empty or only non-Google channels. No tokens.

### Reset deletion

- Delete `core/ops/ze-onboarding/ze_onboarding/reset.py` and its export, the `reset_service` wiring in `ze_api/wiring/container.py`, `scripts/reset_personal_state.py`, the Makefile target and its help line, `apps/ze-api/tests/onboarding/test_reset.py`, and the `docs/onboarding.md` paragraph (it then points to `make db-reset` + `make db-reset-seed`).

## Project Structure

### Documentation (this feature)

```text
specs/phases/194-accountability-surfaces/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/rest.md
└── checklists/requirements.md
```

### Source Code

```text
core/cognition/ze-memory/ze_memory/action_records/{types.py,store.py}
core/cognition/ze-worldstate/ze_worldstate/store.py
plugins/ze-personal/ze_personal/channels/{watermark_store.py,types.py} ; plugins/ze-personal/ze_personal/migrations/versions/zc040_channel_poll_outcome.py
plugins/ze-messenger/ze_messenger/jobs/inbound_poll.py
apps/ze-api/ze_api/api/v0/{actions,collisions,channels}/ (new) ; apps/ze-api/ze_api/api/v0/system/models.py (new)
apps/ze-api/ze_api/api/v0/{__init__.py,loops/router.py} ; apps/ze-api/ze_api/api/eval/{__init__.py,collisions.py (deleted),schemas.py}
core/ops/ze-onboarding/ze_onboarding/{reset.py (deleted),__init__.py} ; apps/ze-api/ze_api/wiring/container.py ; scripts/reset_personal_state.py (deleted) ; Makefile
packages/ze-client/src/generated/*
```

## Docs touched

- `docs/native-interface.md`: REST surfaces `listActionRecords`, `listCollisions`, `getModelSettings`, `listChannelStatus`, `listLoops?since`.
- `docs/memory.md`: ledger read by subject.
- `docs/system-one.md`: the tier settings route.
- `docs/onboarding.md`: reset paragraph replaced by the database reset.
- `docs/architecture.md`: REST table; migration table row for `zc040`.
- `CONTRIBUTING.md` / `README.md` if they mention `reset-personal-state` (grep at T001).
- `AGENTS.md`: phase row 194; migration ownership row for ze-personal (`user_channel_watermarks.last_outcome`, `zc040`); `specs/README.md` row 194.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004):
- **Pydantic response schemas** for all five surfaces in their new package `schemas.py` files (`api/v0/actions/schemas.py`, `api/v0/collisions/schemas.py`, `api/v0/channels/schemas.py`, `api/v0/system/schemas.py` additions), with route stubs returning 501 under their final operation ids.
- **Router registration** in `api/v0/__init__.py`, and the `since` query added to `listLoops` as a pass-through stub.
- **Domain type stubs**: `ActionSubjectKind` (ze-memory types), `PollOutcome` and `ChannelPollStatus` (ze-personal types), and the `list_by_subject` / `record_outcome` / `get_status_many` Protocol signatures.
- `make codegen`.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `api/v0/__init__.py`, all new `schemas.py` files, the domain type stubs, `packages/ze-client/src/generated/*`; merges and gates | T001–T004, T019, T020 | - | Gauge |
| ledger | Sonnet ENG | `ze_memory/action_records/store.py` (body), `api/v0/actions/router.py`, their tests | T005–T007 | contract step | floor Reviewer |
| reads | Sonnet ENG | `api/v0/collisions/router.py`, `api/eval/{__init__,collisions,schemas}.py`, `api/v0/system/models.py`, `ze_worldstate/store.py`, `api/v0/loops/router.py`, their tests | T008–T012 | contract step | floor Reviewer |
| channels | Sonnet ENG | `zc040` migration, `ze_personal/channels/watermark_store.py` (body), `ze_messenger/jobs/inbound_poll.py` (and the webhook watermark line if any), `api/v0/channels/router.py`, their tests | T013–T016 | contract step | floor Reviewer |
| jr1 | Haiku JR | the reset deletion: `ze_onboarding/reset.py`, `ze_onboarding/__init__.py`, `ze_api/wiring/container.py` (reset lines only), `scripts/reset_personal_state.py`, `Makefile` (two lines), `apps/ze-api/tests/onboarding/test_reset.py` | T017 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" | T021–T023 | lanes merged | floor Reviewer |

**Rules**: one lane per file. `ze_api/wiring/container.py` is touched only by `jr1` (reset lines). `lead` merges in the order ledger, reads, channels, jr1, re-runs `make codegen`, then runs the gates. `jr1`'s task is a fully specified deletion with its grep check written in the task.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| `zc040` migration | "Needs re-auth" (spec US5) cannot be read from anything stored: poll failures are only logged. | A stale-sync heuristic (it cannot tell expired credentials from no new mail); an in-memory flag (lost on restart, and the user reads Governance after a restart). |
