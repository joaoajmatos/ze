# Data Model: Loop Track Tool

No table or column changes.

## New types (`ze_worldstate/types.py`)

```python
class TrackOutcome:           # plain string constants, like LoopProvenance
    CREATED = "created"
    CONFIRMED = "confirmed"
    REINFORCED = "reinforced"
    REVIVED = "revived"

@dataclass
class TrackResult:
    ok: bool
    outcome: str | None = None
    loop: OpenLoop | None = None
    error: str | None = None
```

## Lifecycle edge

```
suspected -> active | dropped
active    -> drifting | closed | dropped
drifting  -> closed | dropped
drifting  -> active            # NEW: only transition(..., user_asked=True)
closed, dropped: terminal
```

`PostgresLoopStore.transition(loop_id, new_state, *, user_asked=False)`: the matrix lookup is `_ALLOWED_TRANSITIONS[state] | (_USER_ASKED_TRANSITIONS[state] if user_asked else set())`. `_USER_ASKED_TRANSITIONS = {DRIFTING: {ACTIVE}}`. Callers that pass nothing keep today's behavior (REST confirm, `review.confirm_loop`, decay, sweep).

## New store method

```python
async def stamp_declared(self, loop_id: UUID, *, confidence: float, deadline: datetime) -> None
```
One statement: `UPDATE open_loops SET confidence=$2, drift_deadline=$3, drift_rationale=NULL, confirmed_at=now(), updated_at=now() WHERE id=$1`. Same `now()` for both columns satisfies `updated_at <= confirmed_at`. Raises `LoopNotFoundError` when no row is updated (check `UPDATE ... RETURNING id`).

## Field values by outcome

| Outcome | state | provenance | claim_kind | confidence | confirmed_at | drift_deadline |
|---|---|---|---|---|---|---|
| created | active | user_declared | PRIORITY | 0.9 | now | now + window |
| confirmed | active | unchanged (e.g. conversation) | unchanged | 0.9 | now | now + window |
| reinforced | unchanged | unchanged | unchanged | max(current, 0.9) | unchanged | unchanged |
| revived | active | unchanged | unchanged | 0.9 | now | now + window; rationale NULL |

`confirmed` and `revived` keep the original provenance: the row records how it first arose; the user's confirmation shows as `confirmed_at` and confidence.
