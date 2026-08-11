# Contract: `PendingConfirmationStore`

Internal interface contract (`core/ze-core/ze_core/conversation/confirmations/store.py`),
consumed by `apps/ze-api/ze_api/api/websocket/{confirmation,turns,endpoint}.py`. No
external WS/REST wire-protocol change — the client already sends/receives `request_id`
(`id` field) today; only the server-side storage key changes.

## Before (current)

```python
async def save(self, thread_id: str, request_id: str, prompt: str,
               actions: list[dict], expires_at: datetime) -> None: ...
    # INSERT ... ON CONFLICT (thread_id) DO UPDATE  -- clobbers any existing row for thread_id

async def get_pending_for_thread(self, thread_id: str) -> dict | None: ...
    # returns at most one row per thread_id

async def clear(self, thread_id: str) -> bool: ...
    # deletes whatever row currently exists for thread_id, regardless of which gate it belongs to
```

## After (this feature)

```python
async def save(self, thread_id: str, request_id: str, prompt: str,
               actions: list[dict], expires_at: datetime) -> None: ...
    # INSERT ... ON CONFLICT (request_id) DO UPDATE  -- request_id is now the PK
    # a second gate on the same thread_id is a distinct row, never overwrites the first

async def get_pending_for_thread(self, thread_id: str) -> list[dict]: ...
    # BREAKING: return type changes from `dict | None` to `list[dict]`
    # returns ALL non-expired pending confirmations for the thread (may be empty, one, or many)

async def get_pending(self, request_id: str) -> dict | None: ...
    # NEW: look up a single gate by its own id — used by handle_confirm to resolve
    # a specific gate rather than "whatever is pending for this thread"

async def clear(self, thread_id: str, request_id: str) -> bool: ...
    # BREAKING: now requires request_id; deletes only the row matching BOTH thread_id
    # and request_id. A stale timeout task can never delete a different gate's row.
```

## Call-site impact

| Call site | Change required |
|---|---|
| `apps/ze-api/ze_api/api/websocket/confirmation.py:handle_confirm` | Already receives `request_id` from `data.get("id")` — pass it through to `clear(thread_id, request_id)` instead of `clear(thread_id)`. |
| `apps/ze-api/ze_api/api/websocket/confirmation.py:confirmation_timeout` | Must be scheduled with the specific `request_id` it guards (new parameter), and call `clear(thread_id, request_id)`. |
| `apps/ze-api/ze_api/api/websocket/turns.py` (line ~125) | `confirmation_store.clear(effective_thread_id)` → needs the `request_id` of the gate being cleared in that code path; verify during implementation which gate this corresponds to. |
| `apps/ze-api/ze_api/api/websocket/connection.py` (`ConnectionManager.connect`, reconnect replay at line ~76-78) | `get_all_pending()` is unaffected (already returns all rows across all threads) — reconnect replay logic itself doesn't need to change, only how it's fed into the rekeyed `pending_configs`. |
| `apps/ze-api/ze_api/api/websocket/endpoint.py` (`pending_configs` dict) | Rekey from `dict[str, dict]` (`thread_id -> config`) to `dict[str, dict]` (`request_id -> config`) + secondary `dict[str, set[str]]` (`thread_id -> {request_id,...}`) per data-model.md. All three call sites that do `pending_configs[thread_id] = result` / `pending_configs.get(thread_id)` / `pending_configs.pop(thread_id, None)` need updating to route through `request_id` (obtained from the gate-open response) with `thread_id` used only to look up candidate `request_id`s. |

## Migration

`core/ze-core/ze_core/migrations/versions/zc0XX_confirmations_request_id_key.py`
(next free `zc` revision number at implementation time):

```sql
ALTER TABLE pending_confirmations DROP CONSTRAINT pending_confirmations_pkey;
ALTER TABLE pending_confirmations ADD PRIMARY KEY (request_id);
CREATE INDEX IF NOT EXISTS ix_pending_confirmations_thread_id
    ON pending_confirmations (thread_id);
```

No data loss on upgrade: existing rows already have a non-null, unique `request_id`
value (it was already being written, just not used as the key), so the `ADD PRIMARY
KEY` is a safe promotion, not a backfill.

Downgrade reverses the constraint swap; note a downgrade after multiple concurrent gates
have been created would violate the restored `PRIMARY KEY (thread_id)` if more than one
row shares a `thread_id` at that time — acceptable since downgrades of this table are
not expected in normal operation (matches existing precedent of other `zc` migrations
in this codebase, which do not special-case downgrade-time data conflicts).
