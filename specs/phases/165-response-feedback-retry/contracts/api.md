# Contracts

## REST (all under `/api/v0`, `require_api_key`, explicit `operation_id`, `response_model`, `summary`, `description`)

### PUT /messages/{message_id}/feedback — `setMessageFeedback`
Body: `{"rating": "up"|"down"|"none", "idempotency_key": "<client uuid>"}`.
200: `FeedbackView`. 404 message not found or not an assistant message. 422 bad rating. Repeating the same `idempotency_key` returns the existing state, appends nothing. `none` on an unrated message is a no-op 200.

### GET /messages/feedback?ids=… — `getMessageFeedback` (max 100 ids)
200: `{"items": [{"message_id", "current": "up"|"down"|null, "history": [{"kind","occurred_at"}], "retry": {"available": bool, "reason_code": str|null, "reason_text": str|null}, "replaces": uuid|null, "replaced_by": uuid|null, "trace_present": bool}]}`. User messages are omitted; every stored assistant message is included, with `trace_present=false` and `retry.reason_code="trace_unavailable"` when it has no trace.

### GET /messages — `listMessages` (changed)
Adds `include_superseded` (default false). `MessageSchema` adds `replaces`, `replaced_by`.

## WebSocket
In: `{"type":"retry","message_id":"<uuid>","thread_id":"<id>"}`.
Out:
- `message` (existing) for the new reply, carrying `replaces`.
- `message_superseded`: `{"type":"message_superseded","message_id","replaced_by","thread_id"}`.
- `error` (existing) gains optional `code`: `retry_unavailable` (with `reason_code`, `reason_text`), `retry_failed`, `busy` (existing detail kept).
`typing` frames flow as in a normal turn. Refusal happens before any graph run.

## Reason codes
`not_latest, has_write_action, has_reversible_action, has_irreversible_action, confirmed_action, workspace_run, trace_unavailable, unknown_tool, turn_pending, busy, disconnected` (`disconnected` is client-side only).
