# Data Model: Concurrent Thread Identity

No new tables.

| Field | Where | Meaning |
|---|---|---|
| `thread_id` | WS frames, sessions, LangGraph | Conversation identity |
| `request_id` | confirmations (113) | Gate identity inside a thread |
| Trace map | Client store | `thread_id` → latest / pending `trace_update` |
| `_abort_tokens` | `Container` | Already `thread_id` → token; do not collapse to one |

`pending_configs` stays `request_id` → graph config. Selection for cancel is “all request_ids for this thread” via existing `thread_pending_requests`.
