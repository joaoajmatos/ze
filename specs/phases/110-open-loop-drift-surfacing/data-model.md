# Phase 1 Data Model: Open-Loop Drift Detection & Surfacing

No new tables. Two new nullable columns on the existing `open_loops` table (owned by
`ze-worldstate`, migration `zw002_drift_columns.py` on the `zw` chain), one new allowed
lifecycle transition, one behavior-preserving change to `link_evidence`'s side effects, and
reuse (by new `event_type` keys, no schema change) of `ze-proactive`'s existing `push_log` table.

## `OpenLoop` (extended)

```python
@dataclass
class OpenLoop:
    title: str
    claim_kind: LoopClaimKind
    provenance: LoopProvenance
    confidence: float
    state: LoopState = LoopState.SUSPECTED
    goal_id: UUID | None = None
    dismissed_evidence_fingerprint: str | None = None
    drift_deadline: datetime | None = None      # NEW — set at confirm-time (review.confirm_loop)
    drift_rationale: str | None = None          # NEW — set on active -> drifting transition
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    confirmed_at: datetime | None = None
    closed_at: datetime | None = None
```

- **`drift_deadline`**: `confirmed_at + timedelta(days=implied_window_days or 7)`, computed once
  when a loop transitions into `active` (whether via `review.confirm_loop` or the
  directly-declared-active path in `extraction.py`). `None` only transiently before that
  transition happens (a `suspected` loop has no deadline yet).
- **`drift_rationale`**: `None` until the loop transitions `active → drifting`; overwritten (not
  appended) on each subsequent drift re-evaluation — Phase A/B do not re-drift an
  already-`drifting` loop (FR-004), so in practice this is write-once per lifecycle, but the
  field is not const to allow a future re-open path without a schema change.

## `open_loops` table (delta)

```sql
ALTER TABLE open_loops
  ADD COLUMN drift_deadline TIMESTAMPTZ NULL,
  ADD COLUMN drift_rationale TEXT NULL;

CREATE INDEX IF NOT EXISTS open_loops_drift_deadline_idx
  ON open_loops (drift_deadline)
  WHERE state = 'active';
```

The partial index keeps the drift sweep's eligibility query
(`WHERE state = 'active' AND drift_deadline <= now() AND updated_at <= confirmed_at`) cheap
without indexing rows in terminal or `drifting` states.

## Lifecycle transition matrix (delta)

`store.py`'s `_ALLOWED_TRANSITIONS` gains exactly one new edge:

```python
LoopState.ACTIVE: {LoopState.DRIFTING, LoopState.CLOSED, LoopState.DROPPED},
```

`ACTIVE → DRIFTING` is only ever invoked by the two drift call sites this feature adds (the
sweep job, `drift.py`; the immediate contradiction path, `decay.py`) — never by user action and
never exposed on the REST transition endpoints, preserving FR-010 (no autonomous transition is
user-triggerable in reverse, and no *other* autonomous transition exists).

## `LoopStore` Protocol (delta)

```python
class LoopStore(Protocol):
    ...
    async def set_drift_deadline(self, loop_id: UUID, deadline: datetime) -> None: ...
    async def set_drift_rationale(self, loop_id: UUID, rationale: str) -> None: ...
    async def list_drift_candidates(self) -> list[OpenLoop]: ...
```

`link_evidence` (existing method, unchanged signature) now also executes
`UPDATE open_loops SET updated_at = now() WHERE id = $1` alongside its existing
`memory_relationships` insert — this is the "fresh evidence" signal `list_drift_candidates`
reads (see research.md §2).

## `PushLogStore` usage (no schema change)

Three distinct `event_type` string keys partition this feature's use of the existing
`ze-proactive` `push_log` table from the correlation engine's own use of it:

| `event_type` key | Written by | Read by |
|---|---|---|
| `worldstate_loop_push` | push sweep, on successful push | push sweep's `within_budget` (sibling daily budget, FR-007) |
| `worldstate_loop_inline:{loop_id}` | inline node, on every inline mention | push sweep's cooldown gate (FR-012) |
| `correlation_push` (existing, unchanged) | `CorrelationPushConsumer` | unchanged — untouched by this feature, proving the budgets are independent |

## `Hypothesis`-shaped surfacing input (new, internal-only, not persisted)

`LoopSurfacer` builds an ephemeral value passed to the extracted `ze_correlation.push` bar
functions — not a new dataclass, just the five positional/keyword primitives those functions
take (`confidence: float`, `summary: str` — the drift rationale text — `evidence_labels:
list[str]` — from `loop_store.list_evidence` resolved to text, same resolution `rest.py`'s
`_fetch_evidence_summaries` already performs — `event_key: str`, and `relevance: float` — scored
via the injected `RelevanceModel` against the loop's linked entity names, `topics=[]`, mirroring
`CorrelationEngine`'s own proactive relevance prefilter). No new persisted type; `relevance` is
computed fresh on every push-check, never stored on `OpenLoop`.

## `SurfacingDecision` (conceptual, not a stored row)

The spec's Key Entities section names a "Surfacing decision" — in this implementation it is not
a new row type; it is the *union* of (a) the transient inline-node return value (rendered into
`state["components"]`/`final_response`, never persisted beyond the existing message/trace
storage `ze-core` already does) and (b) a `push_log` row (above) for the push path. No new table
is introduced for it, consistent with the spec's own note that this "reus[es] the correlation
engine's existing push-log pattern for the push path."
