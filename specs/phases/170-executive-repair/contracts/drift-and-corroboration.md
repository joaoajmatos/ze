# Contract: Drift and corroboration

## Store

```python
class LoopStore(Protocol):
    async def list_drift_candidates(self) -> list[OpenLoop]: ...
    async def record_corroboration(
        self, loop_id: UUID, *, window_days: int = DEFAULT_DRIFT_WINDOW_DAYS
    ) -> None: ...
```

`DEFAULT_DRIFT_WINDOW_DAYS` stays in `ze_worldstate/drift.py` (7). The store imports it; no circular import (`drift.py` imports types only).

### `list_drift_candidates`

```sql
SELECT * FROM open_loops
WHERE state = 'active'
  AND drift_deadline IS NOT NULL
  AND drift_deadline <= now()
```

No other column participates. `ORDER BY drift_deadline ASC` is allowed (stable sweep order).

### `record_corroboration`

```sql
UPDATE open_loops
SET drift_deadline = GREATEST(COALESCE(drift_deadline, now()),
                              now() + make_interval(days => $2)),
    updated_at = now()
WHERE id = $1 AND state = 'active'
```

- No row updated is not an error (loop closed, drifted or dropped meanwhile). No exception, no log above debug.
- It never lowers a deadline (`GREATEST`).
- It does not touch `confirmed_at`, `confidence`, `state` or `drift_rationale`.

## Who calls it

| Caller | When |
|---|---|
| `extraction._create_suspected_loop`, existing-match branch | the match is `active` and the call brought at least one evidence ref |
| `extraction._commit_admitted`, declared branch (new dedup, FR-012) | a match exists and the call brought at least one evidence ref |

Not called by: `create`, `_create_declared_loop` first link, `review.confirm_loop`, `decay.cascade_from_evidence`, 169's `stamp_declared` (which sets its own deadline), the sweep.

## Sweep

```python
async def run(self) -> None:
    for loop in await self._loop_store.list_drift_candidates():
        if not drift.is_drift_eligible(loop):      # defensive re-check
            continue
        await self._loop_store.transition(loop.id, LoopState.DRIFTING.value)
        await self._loop_store.set_drift_rationale(loop.id, drift.compose_absence_rationale(loop))
```

`is_drift_eligible(loop, now)`: `loop.state is ACTIVE and loop.drift_deadline is not None and loop.drift_deadline <= now`. A naive datetime is treated as UTC.

`compose_absence_rationale(loop)`: "No corroborating evidence (email, calendar, or conversational update) before the implied window elapsed on {deadline date}." (`unknown` when no deadline.)

`transition` ACTIVE → DRIFTING raises `InvalidLoopTransitionError` if the loop changed state since the list; the sweep catches it per loop, logs `open_loop_drift_skipped` at info, and continues.

## Postgres test matrix (`tests/pg/test_drift.py`)

| Case | Expect |
|---|---|
| declared loop via `_create_declared_loop` path (create + `set_drift_deadline`), deadline moved to `now() - 1 day` | candidate; sweep → `drifting` |
| suspected → `review.confirm_loop`, deadline moved back | candidate; sweep → `drifting` |
| active, deadline `now() + 1 day` | not candidate |
| `record_corroboration` on active with past deadline | deadline ≥ now + 7 days; not candidate |
| `record_corroboration` with a deadline already 30 days out | deadline unchanged |
| `record_corroboration` on `drifting` / `closed` / `suspected` | no row changed, no error |
| revive (169 `transition(user_asked=True)` + `stamp_declared`) then deadline moved back | candidate again (skipped with `pytest.skip` if 169 is not on the branch) |
| two active loops, one past deadline | only that one drifts |

Fast-forward time by `UPDATE open_loops SET drift_deadline = ...`, never by sleeping.
