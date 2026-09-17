# Contract: Concurrent thread identity

Identifiers: `thread_id`, `request_id`, `4000`, `trace_update`, `try_set_busy`, `pending_configs`, `thread_pending_requests`.

## Shipped (do not regress)

- One `_ws`; per-thread `ThreadSlot.busy`
- `asyncio.create_task` for messages so other threads accept input
- Confirm frames include `thread_id` + `id` (`request_id`)
- Client `thinkingThreads` / `attentionThreads`

## 159 must change

| Leak | Required |
|---|---|
| Trace store applies every `trace_update` | Apply only if `frame.thread_id` matches the open thread **or** store a map and select by active `thread_id` |
| `handle_command` uses first pending config | Require `thread_id`; abort only that thread |
| Promote/timeout notice | Include `thread_id` on WS/ntfy |

## Forbidden

- Remove 4000 displace
- Reconnect on `selectSession`
- Second WebSocket per conversation
