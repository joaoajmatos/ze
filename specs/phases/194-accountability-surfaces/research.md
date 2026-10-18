# Research: Accountability Surfaces (B4)

## R1. Matching an action to its subject
- **Decision**: match on the record's `context` JSON keys only: goal → `goal_id`, workflow → `workflow_id`, workflow run → `workflow_run_id`, workspace run → `workspace_run_id`.
- **Rationale**: producers already stamp these (`ze_automation/action_records.py` sets `goal_id`/`milestone_id`, `workflow_id` + `workflow_run_id`, or `workflow_run_id` alone; `ze_workspace/action_handoff.py` sets `workspace_run_id`). One producer path writes only `workflow_run_id`; those records list under their run, and under the workflow only if a later change stamps `workflow_id` there too (noted for the implementer at T005: add `workflow_id` at that producer if the workflow id is in scope there; it is in `ze-automation`, outside this phase's lanes, so record it as a follow-up instead of editing).
- **Alternatives**: join through `workflow_executions` to map runs to workflows (cross-package SQL from ze-memory into automation tables: violates ownership).

## R2. Index
- **Decision**: no new index by default. T001 runs `EXPLAIN` on the dev database; add an expression index (`zm025`) only if the filtered query scans more than a few thousand rows.
- **Rationale**: single user, tens of records a day.

## R3. Paging
- **Decision**: keyset on `(occurred_at DESC, id DESC)`; the cursor is base64 of `occurred_at.isoformat()|id`; invalid cursor → 422.
- **Rationale**: stable under inserts; matches the memory feed's cursor style.

## R4. "Last change" for loops
- **Decision**: `open_loops.updated_at`, which every state transition, confirm, drift, corroboration and stamp statement already sets (`ze_worldstate/store.py`).

## R5. Needs re-auth
- **Decision**: record each poll's outcome on `user_channel_watermarks` (`zc040`); `auth_failed` when the exception chain contains `google.auth.exceptions.RefreshError` (expired or revoked refresh token), else `failed`.
- **Rationale**: nothing stores poll failures today (`inbound_poll.py` logs `inbound_poll_failed` and returns). The old channels route (deleted in cf-06) showed only `last_polled_at` and `poll_enabled`.
- **Alternatives**: a stale-watermark heuristic (cannot tell an expired token from a quiet inbox).

## R6. Tier settings source
- **Decision**: read `complexity_surface_config(container.settings)` and `resolve_agent_model(name, tier, app_config)` from `ze_core/routing/tier.py`, the functions `choose_tier` uses, on every request.
- **Rationale**: one source (FR-004); SIGHUP reload is reflected without restart.

## R7. Eval client for collisions
- **Finding**: no eval client or MCP tool calls `/collisions` (grep `core/ops/ze-eval`, `eval/`); only ze-api tests do. Moving the route needs no eval change beyond tests.
