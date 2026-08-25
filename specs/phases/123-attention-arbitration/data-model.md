# Phase 1 Data Model: Attention Arbitration

No new database tables (Assumptions, spec.md). Everything below is in-memory
dataclasses (`core/ze-priority/ze_priority/types.py`) computed fresh per query, plus
one new module in `core/ze-proactive` wrapping the existing `push_log` table under a
new shared event key.

## PriorityItem

The per-item row of a `PriorityView` ranking. Not persisted.

| Field | Type | Notes |
|---|---|---|
| `source_kind` | `Literal["loop", "goal", "hypothesis"]` | Which mechanism produced this item — plugin/mechanism-domain vocabulary, a plain string literal, not a core enum extension point (Constitution III). |
| `claim_kind` | `ze_agents.claims.ClaimKind` | Loops and hypotheses: read off the source entity as-is (`OpenLoop.claim_kind`, `Hypothesis.claim_kind`) — not invented here. Goals: `Goal`/`Milestone`/`VerificationGate`/`StuckGoal` carry no claim-kind field of their own (confirmed against `ze-automation`'s types), so `PriorityView` assigns `ClaimKind.PRIORITY` directly — permissible per FR-004, since `Priority` is the one claim-kind only the executive function (this projection) is licensed to produce. |
| `source_id` | `UUID` | The originating `OpenLoop.id` / goal id / `Hypothesis.id`. |
| `title` | `str` | Human-readable label, taken from the source entity (`OpenLoop.title`, `Goal.title`, `Hypothesis.summary`). |
| `signal` | `SourceSignal` | The mechanism-specific value this item's score was derived from (see below) — carried through for explainability (FR-002), not recomputed. |
| `priority` | `ze_agents.claims.Confidence` | The resolved, comparable score (FR-002). |
| `rank` | `int` | 1-indexed position in the final ordered list; assigned after sort + tie-break. |
| `activity_at` | `datetime` | The timestamp used for deterministic tie-break (loop `updated_at`, goal reference timestamp, hypothesis `created_at`). Not part of the score itself. |

## SourceSignal (discriminated union, one variant per source)

Carries the *original* per-source value straight through, so `PriorityItem.signal`
never re-expresses a source's computation in a new shape — it's the same value the
source already returns.

```python
@dataclass
class LoopSignal:
    state: LoopState              # ze_worldstate.types.LoopState
    confidence: float             # OpenLoop.confidence, as-is
    drift_deadline: datetime | None

@dataclass
class GoalSignal:
    kind: Literal["active", "awaiting_gate"]   # StuckGoal.kind, as-is
    idle_days: int                              # StuckGoal.idle_days, as-is

@dataclass
class HypothesisSignal:
    confidence: float             # Hypothesis.confidence, as-is
    relevance: float              # Hypothesis.relevance, as-is

SourceSignal = LoopSignal | GoalSignal | HypothesisSignal
```

## PriorityRanking

The full `PriorityView` query result.

| Field | Type | Notes |
|---|---|---|
| `items` | `list[PriorityItem]` | Ordered highest-priority first (FR-001, FR-002). |
| `sources_succeeded` | `set[Literal["loop", "goal", "hypothesis"]]` | Which sources answered — lets a caller distinguish "no open items" from "that source errored" (FR-009). |
| `sources_failed` | `set[Literal["loop", "goal", "hypothesis"]]` | Sources that raised and were excluded from ranking rather than failing the whole query (FR-009, Edge Cases). |
| `generated_at` | `datetime` | When this ranking was computed — not persisted, informational only. |

## PriorityView (query object)

```python
class PriorityView:
    def __init__(
        self,
        loop_store: LoopStore,
        goal_store: GoalStore,
        hypothesis_store: HypothesisStore,
    ) -> None: ...

    async def rank(self) -> PriorityRanking:
        """Read-only. Degrades per-source on error (FR-009), raising
        ZePriorityError only if all three sources fail. Never recomputes
        drift/goal-idleness/novelty — only wraps each source's existing signal
        into a Confidence and sorts (FR-003)."""
```

State transitions: none — `PriorityView` is stateless and computed fresh per call
(Key Entities, spec.md).

## SharedAttentionBudget (core/ze-proactive/ze_proactive/attention_budget.py)

Replaces the two independently-configured budgets (FR-005). Wraps the existing
`PushLogStore`; no schema change.

```python
ATTENTION_PUSH_EVENT_KEY: Final[str] = "attention_push"

async def within_budget(
    push_log: PushLogStore,
    max_per_day: int,
    *,
    window_hours: float = 24.0,
) -> bool:
    """Moved from ze_correlation.push (FR-006). Uses ATTENTION_PUSH_EVENT_KEY —
    callers no longer pass their own event_type; there is exactly one shared one."""

async def try_claim_shared(
    push_log: PushLogStore,
    source_kind: Literal["loop", "goal", "hypothesis"],
    source_id: UUID,
    *,
    payload: str | None = None,
) -> bool:
    """Atomic claim (FR-008): idempotency_key = f"{source_kind}:{source_id}" against
    ATTENTION_PUSH_EVENT_KEY. Relies on push_log's existing unique index — same
    claim-then-notify pattern LoopSurfacer already uses, generalized to one shared key."""

async def release_shared(
    push_log: PushLogStore,
    source_kind: Literal["loop", "goal", "hypothesis"],
    source_id: UUID,
) -> None: ...
```

## AttentionArbitrationJob (core/ze-priority/ze_priority/arbitration.py)

Not a data entity, but the one call site that ties `PriorityView` and
`SharedAttentionBudget` together (FR-007). Sequence per sweep:

1. Ask `ze-worldstate`'s `LoopSurfacer` and `ze-correlation`'s push consumer for
   their currently push-*eligible* candidates (new methods that apply each
   mechanism's existing novelty/relevance/idempotency bar but stop short of
   sending — SC-004 requires this bar to keep working unchanged).
2. Rank the combined eligible candidates via `PriorityView.rank()` (or a
   `PriorityView.rank_subset()` variant scoped to just the eligible ones — TBD at
   task-breakdown time, not a data-model concern).
3. For the single top-ranked eligible item: `try_claim_shared(...)`. On success,
   delegate to that mechanism's existing send function; on failure (lost a race),
   move to the next-ranked eligible item and retry the claim.
4. All non-winning eligible items are logged as budget-arbitrated (Acceptance
   Scenario, User Story 2) rather than silently dropped — this is a log-level
   concern, not a new persisted field.

## Validation rules

- `PriorityRanking.items` is never empty *and* `sources_failed` empty at the same
  time as all three sources returning zero items — an empty ranking with all
  sources succeeded is valid (Edge Cases: "nothing open" must not error).
- `PriorityItem.rank` is contiguous starting at 1 with no gaps or duplicates within
  one `PriorityRanking`.
- `try_claim_shared` must never return `True` for two concurrent callers racing the
  same day's last slot (FR-008) — enforced by the existing `push_log` unique index,
  not application-level locking.
