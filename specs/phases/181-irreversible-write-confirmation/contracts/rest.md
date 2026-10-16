# Contract: REST surface changes

All routes keep the `/api/v0/` prefix, `HTTPBearer` auth, explicit `operation_id`, `response_model`, `summary` and `description` (phase 7/73 rules).

## Removed

| Method | Path | operation_id |
|---|---|---|
| GET | `/api/v0/capabilities` | (current id in `routes/capabilities.py`) |
| PUT/POST/DELETE | `/api/v0/capabilities/...` | all routes in `routes/capabilities.py` |

The `capabilities` OpenAPI tag, the `/capabilities` WS command (`websocket/commands.py`) and ze-web's command button go with them.

## Added: held writes (routes: new `apps/ze-api/ze_api/api/routes/held_writes.py`; query functions in `ze_automation/rest.py`; Pydantic models in `ze_api/api/schemas.py`)

### `GET /api/v0/held-writes`
- operation_id `listHeldWrites`; query `status` (default `open`).
- 200 `HeldWriteListResponse { items: HeldWriteOut[] }`.
- `HeldWriteOut { request_id, source: "workflow"|"goal", source_name, owner_ref, items: ConfirmItemOut[], status, created_at, expires_at }` (`ConfirmItemOut` mirrors the WS item).

### `POST /api/v0/held-writes/{request_id}/decision`
- operation_id `decideHeldWrite`; body `HeldWriteDecisionIn { choice: "approve"|"deny", edits?: {item_id: text} }`.
- 200 `HeldWriteOut` (status `approved` or `denied`); the run resumes in the background.
- 404 unknown id; 409 not open (already decided or expired).

## Added: eval confirm (owner: ze-api `routes/eval.py`, eval-only, same guard as the other eval routes)

### `POST /eval/confirm`
- Unversioned, like `/eval/chat`. operation_id `evalConfirm`; body `{ session_id, choice: "approve"|"deny", edits? }`; the route prefixes `eval-` to `session_id` exactly as `/eval/chat` does, then answers that thread's open confirmation. 409 when it has none, 422 on a bad choice.
- 200 the same turn-result shape the eval chat route returns (response, tool calls with `parked`/`gate`, `pending_confirmation`).

## Changed: eval tool-call shape

`is_draft: bool` → `parked: bool` and `gate: str` on each tool call in eval responses.

## Changed: workflow step edit (`PATCH` in `apps/ze-api/ze_api/api/routes/workflows.py`)

The request gains `approve_writes: bool` (default `false`). The response gains `writes_needing_approval: [{step_id, agent, tools: [str]}]` for changed steps whose agent has asks-first tools. With `approve_writes=false` the changed steps' `approved_writes` are cleared; with `true` they are set to the listed tools. No ze-web screen calls this route today (`updateWorkflowSteps` has no caller in `apps/ze-web/src`), so no web change; an API caller re-sends with `approve_writes=true` to grant.
