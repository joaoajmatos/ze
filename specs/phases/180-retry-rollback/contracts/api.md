# Contracts: Retry Rollback

All REST changes keep the OpenAPI rules (`response_model`, `summary`, `description`, explicit `operation_id`). Regenerate `@myguyze/ze-client` and WS types with `make codegen`.

## REST

`GET /api/v0/messages/feedback?ids=` (`getMessageFeedback`, unchanged route) — `FeedbackView` changes:

```jsonc
{
  "message_id": "…",
  "retry": {
    "available": true,
    "reason_code": null,
    "reason_text": null,
    "plan": [                       // new; empty for a text-only retry
      {"entry_id": "9f2c1a0b7d3e4f51", "tool": "set_reminder",
       "effect_phrase": "set a reminder", "undo_note": "Does not recall a notification already shown"}
    ]
  },
  "rollback": null                  // new: RollbackRecordResponse | null
}
```

`RollbackRecordResponse`: `{state, entries: [{entry_id, tool, effect_phrase, outcome, at, failure_code}], replaced_by}`.

`GET /api/v0/messages` (`listMessages`): `MessageSchema` gains `rollback: RollbackRecordResponse | null`. A message with `rollback.state != "superseded"` is visible by default (it was not replaced).

Reason codes in `retry.reason_code`: add `not_undoable`, `undo_failed`; remove `has_reversible_action`, `has_write_action`.

## WebSocket in

```jsonc
{"type": "retry", "message_id": "…", "thread_id": "…",
 "confirmed_plan": ["9f2c1a0b7d3e4f51"]}   // new; null or omitted when the plan is empty
```

## WebSocket out

- `error` with `code: "retry_unavailable"` and `reason_code` in {…eligibility codes, `plan_changed`, `undo_not_confirmed`}: nothing changed. With `plan_changed` the frame also carries `plan` (the recomputed public plan) so the client can ask again.
- `error` with `code: "retry_partial"` (new): `{message_id, rolled_back: true, rollback}`; the original reply stays.
- `error` with `code: "retry_failed"`: gains `rolled_back: bool` and `rollback` (when true).
- `message_rollback` (new): `{type, message_id, thread_id, rollback}` whenever the stored record changes.
- `message_superseded`: unchanged; also sent after a paused retry resolves with a reply.
- `confirmation`: unchanged shape; may now follow a `retry` frame.
