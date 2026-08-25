# Contract: PriorityView + Shared Attention Budget (internal Python interface)

No REST/API surface (spec.md Assumptions — internal call sites only: proactive jobs
today, an eventual "what's open" summary is a follow-on concern). This document is
the internal interface contract other packages code against.

## `ze_priority.view.PriorityView`

```python
class PriorityView:
    def __init__(
        self,
        loop_store: LoopStore,
        goal_store: GoalStore,
        hypothesis_store: HypothesisStore,
    ) -> None: ...

    async def rank(self) -> PriorityRanking:
        """
        Returns a single ranking spanning all three sources, highest priority
        first. Never raises on a single source's failure — that source is
        recorded in PriorityRanking.sources_failed and excluded, per FR-009.
        Only raises if ALL three sources fail.
        """

    async def rank_subset(
        self,
        candidates: Sequence[PriorityCandidateRef],
    ) -> PriorityRanking:
        """
        Same ranking logic as rank(), but scoped to an explicit set of
        already-fetched candidate refs (used by AttentionArbitrationJob, which
        has already pulled each mechanism's push-eligible subset and doesn't
        need PriorityView to re-query the full stores).
        """
```

**Preconditions**: none — safe to call with all sources empty.

**Postconditions**:
- `result.items` sorted by `priority.value` descending, ties broken by
  `activity_at` descending then `source_id` ascending (deterministic — Edge Cases).
- `len(result.items) == sum(len(items) per succeeded source)`.
- `result.sources_failed` is empty in the common case; non-empty only when a store
  call raised.

**Errors**: raises `ZePriorityError` (subclass of `ZeError`) only when every source
fails — callers (e.g. a REST route added later, or `AttentionArbitrationJob`) decide
whether that's fatal for their use case.

## `ze_proactive.attention_budget`

```python
async def within_budget(
    push_log: PushLogStore,
    max_per_day: int,
    *,
    window_hours: float = 24.0,
) -> bool: ...

async def try_claim_shared(
    push_log: PushLogStore,
    source_kind: Literal["loop", "goal", "hypothesis"],
    source_id: UUID,
    *,
    payload: str | None = None,
) -> bool:
    """Atomic. True = claim won, caller may send. False = budget exhausted or
    another caller already claimed this exact (source_kind, source_id) today."""

async def release_shared(
    push_log: PushLogStore,
    source_kind: Literal["loop", "goal", "hypothesis"],
    source_id: UUID,
) -> None:
    """Caller must release on send failure, mirroring the existing
    LoopSurfacer.release_push_claim pattern, so a failed send doesn't
    permanently burn that day's budget slot."""
```

**Preconditions**: `push_log` is the shared singleton `PushLogStore` (there is
exactly one — no per-mechanism instance).

**Postconditions**: at most `max_per_day` successful claims against
`ATTENTION_PUSH_EVENT_KEY` within any rolling `window_hours` window, enforced by the
`push_log` unique index — never by application-level check-then-act (FR-008).

## `ze_priority.arbitration.AttentionArbitrationJob`

```python
class AttentionArbitrationJob(ProactiveJob):   # ze_proactive.ProactiveJob
    job_id = "attention_arbitration_sweep"

    def __init__(
        self,
        priority_view: PriorityView,
        loop_surfacer: LoopSurfacer,
        correlation_push_source: CorrelationPushCandidateSource,  # new, ze-correlation
        push_log: PushLogStore,
        max_pushes_per_day: int,
    ) -> None: ...

    async def run(self) -> None:
        """
        1. Gather eligible candidates from loop_surfacer and
           correlation_push_source (each applies its own existing eligibility
           bar — novelty, relevance, prior-idempotency — unchanged, SC-004).
        2. priority_view.rank_subset(candidates).
        3. For each candidate in ranked order: try_claim_shared(...); on True,
           delegate to that source's existing send function and stop; on
           False (budget exhausted), stop — log remaining candidates as
           budget-arbitrated, not silently dropped (User Story 2).
        """
```

Supersedes `ze_worldstate.jobs.push_sweep.PushSweepJob` and `ze-correlation`'s
autonomous scheduled push trigger — both are removed from `apps/ze-api`'s job
registration (`compose.py`) in favor of this one job.
