# Contract: `PushLogStore` idempotent claim

Internal interface contract (`core/ze-proactive/ze_proactive/push_log_store.py`),
consumed by `core/ze-worldstate/ze_worldstate/surfacing.py` (`LoopSurfacer`) and
`core/ze-worldstate/ze_worldstate/jobs/push_sweep.py` (`PushSweepJob`).

## Before (current)

```python
async def log(self, event_type: str, payload: str | None = None) -> None: ...
    # plain INSERT, always succeeds, no exclusivity

# LoopSurfacer.log_push:
async def log_push(self, loop_id: UUID, rationale: str) -> None:
    await self._push_log.log(PUSH_EVENT_KEY, payload=rationale)
    # caller (PushSweepJob.run) always proceeds to self._notifier.push(...) BEFORE this call today —
    # i.e. the notification is sent regardless of whether the log write "wins"
```

## After (this feature)

```python
async def try_claim(self, event_type: str, idempotency_key: str,
                     payload: str | None = None) -> bool:
    """Insert with idempotency_key; return True if this call won the claim,
    False if (event_type, idempotency_key) was already claimed by another writer.
    Never raises on a unique-violation — that is the expected 'lost the race' path."""
    try:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO push_log (event_type, payload, idempotency_key) "
                "VALUES ($1, $2, $3)",
                event_type, payload, idempotency_key,
            )
        return True
    except asyncpg.UniqueViolationError:
        return False

# log() is unchanged — still used by every other event_type with no idempotency_key.
```

## Call-site change: `LoopSurfacer` / `PushSweepJob`

The ordering flips from "notify, then log" to "claim, then notify" so the DB write is
the gate, not an after-the-fact record:

```python
# ze_worldstate/surfacing.py — LoopSurfacer

async def claim_push(self, loop_id: UUID, rationale: str) -> bool:
    """Replaces log_push(). Returns True if this call may proceed to notify."""
    return await self._push_log.try_claim(
        PUSH_EVENT_KEY, idempotency_key=str(loop_id), payload=rationale
    )
```

```python
# ze_worldstate/jobs/push_sweep.py — PushSweepJob.run

passes = await self._surfacer.passes_push_bar(...)
if not passes:
    continue

current = await self._loop_store.get(loop.id)
if current is None or current.state != LoopState.DRIFTING:
    continue

claimed = await self._surfacer.claim_push(loop.id, loop.drift_rationale)
if not claimed:
    log.info("open_loop_push_already_claimed", loop_id=str(loop.id))
    continue  # another concurrent run already sent this — skip silently, not an error

body = format_hedged_mention(loop.title, loop.drift_rationale)
await self._notifier.push(body, urgency="normal")
log.info("open_loop_pushed", loop_id=str(loop.id))
```

The claim now happens **before** `self._notifier.push(...)`, so a losing concurrent run
never sends a notification at all — not even a redundant one that's merely logged twice.

## Migration

`core/ze-proactive/ze_proactive/migrations/versions/zproXXX_push_log_idempotency.py`
(next free `zpro` revision number at implementation time):

```sql
ALTER TABLE push_log ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS ux_push_log_event_idempotency
    ON push_log (event_type, idempotency_key);
```

Postgres unique indexes treat `NULL` values as distinct from one another, so this index
is a no-op constraint-wise for every existing row and every existing caller of
`log()` that doesn't pass an `idempotency_key` (workflow failures, correlation pushes,
etc. — verified against current callers in `core/ze-correlation/ze_correlation/push.py`
and other `push_log_store.log(...)` call sites, none of which are touched by this
migration).

Downgrade drops the index and column; no data loss beyond the key itself (event history
in `event_type`/`payload`/`sent_at` is untouched).
