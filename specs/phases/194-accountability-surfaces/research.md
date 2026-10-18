# Research: Accountability Surfaces (B4)

## R1. Matching an action to its subject
- **Decision**: match on the record's `context` keys through a closed map (goal → `goal_id`, workflow → `workflow_id`, workflow run → `workflow_run_id`, workspace run → `workspace_run_id`). The workflow-finished record gains `workflow_id`: `finish_execution` returns it with `UPDATE … RETURNING workflow_id`, and `emit_workflow_finished` stamps it (review A-1).
- **Rationale**: `emit_workflow_started` stamps `workflow_id`, but `emit_workflow_finished` stamped only the run. A workflow's list would have shown each "started" record and never the outcome. Calendar, reminder and prospecting producers stamp only their own keys; that limit is stated in the spec.
- **Alternatives**: joining runs to workflows across packages (violates table ownership).

## R2. Index
- **Decision**: no new index by default. T001 runs `EXPLAIN` on the dev database; add an expression index (`zm025`) only if the filtered query scans more than a few thousand rows.
- **Rationale**: single user, tens of records a day.

## R3. Paging
- **Decision**: keyset on `(occurred_at DESC, id DESC)`; the cursor is base64 of `occurred_at.isoformat()|id`; invalid cursor → 422.
- **Rationale**: stable under inserts; matches the memory feed's cursor style.

## R4. "Last change" for loops
- **Decision**: `open_loops.updated_at`, which every state transition, confirm, drift, corroboration and stamp statement already sets (`ze_worldstate/store.py`).

## R5. Needs re-auth
- **Decision**: record each poll's outcome on `user_channel_watermarks` (`zc040`). An outcome is an UPDATE when the row exists. Otherwise it is an INSERT with `last_polled_at = now() - DEFAULT_LOOKBACK`, so a later success does not skip the failure window. On failure the poll job first upserts the `user_channels` row, as the success path does, so the FK holds and the channel is listed. `auth_failed` comes from ze-google's `is_auth_failure(exc)`, which walks `__cause__` and `__context__` up to depth 5 for `RefreshError`, so the plugin never imports `google.auth`. Otherwise the outcome is `failed`. Push channels report `unknown`, because the webhook path swallows errors and watches lapse (review C-1, C-2, C-3).
- **Rationale**: nothing stores poll failures today (`inbound_poll.py` logs `inbound_poll_failed` and returns). The old channels route (deleted in cf-06) showed only `last_polled_at` and `poll_enabled`.
- **Alternatives**: a stale-watermark heuristic (cannot tell an expired token from a quiet inbox).

## R6. Tier settings source
- **Decision**: read `complexity_surface_config(container.settings)` and `resolve_agent_model(name, tier, app_config)` from `ze_core/routing/tier.py`, the functions `choose_tier` uses, on every request.
- **Rationale**: one source (FR-004); SIGHUP reload is reflected without restart.

## R7. Eval client for collisions
- **Finding**: no eval client or MCP tool calls `/collisions` (grep `core/ops/ze-eval`, `eval/`); only ze-api tests do. Moving the route needs no eval change beyond tests.
