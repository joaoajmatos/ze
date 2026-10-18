# Contracts: Accountability Surfaces (B4)

All routes: `Authorization: Bearer <ZE_API_KEY>`, `response_model`, `summary`, `description`, `operation_id`.

## `GET /api/v0/actions` — `listActionRecords`
Query: `subject_type` (goal|workflow|workflow_run|workspace_run), `subject_id` (UUID; required with `subject_type` and only with it), `since` (datetime), `cursor` (opaque), `limit` (1..200, default 50).
200 `ActionRecordPage`; 422 for a lone subject_type/subject_id, a bad cursor or a limit out of range.

## `GET /api/v0/collisions` — `listCollisions`
Unchanged query (`entity_id`, `source_function`, `since`, `until`, `limit` 1..200) and response, now on the product router. An unknown `source_function` → 422. The dev/eval copy is gone (404).

## `GET /api/v0/system/models` — `getModelSettings`
200 (`complexity_enabled` = enabled AND a bar is set) `{ "complexity_enabled": true, "simple_max": 0.40, "agents": [{ "name": "calendar", "model": "…", "model_simple": "…" | null }] }`. No secrets.

## `GET /api/v0/loops?since=<datetime>` — `listLoops`
`state` is repeatable (`?state=closed&state=dropped`); new optional `since`: loops whose `updated_at` is after it.

## `GET /api/v0/channels/status` — `listChannelStatus`
200 `{ "google_configured": true, "channels": [{ "channel_id": "gmail:me@x", "channel_type": "email", "handle": "me@x", "display_name": null, "state": "connected|needs_reauth|error|off|unknown", "last_sync_at": "…" | null, "push": false }] }`. Push channels → `unknown` ("Receives by push; Ze does not monitor it."); registry inbound channels not yet in `user_channels` are listed too. No tokens.
