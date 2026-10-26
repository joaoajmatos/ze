# Contract: the push bar, its sources and arbitration (`ze-priority`)

Owners: lane `bar` (`push_bar.py`, `arbitration.py`, the two sources), lane `conv` (`turn.py`, `surfacing_memory.py`). Types `PushCandidate` and `BarThresholds` come from lane `lead` (`ze_proactive/candidates.py`, see [notifier.md](notifier.md)).

## `ze_priority/push_bar.py` (lane `bar`)

```python
class PushHistory(Protocol):
    async def recent_discretionary_bodies(self, hours: float) -> list[str]: ...
    # ProactiveNotifier satisfies it.

class MentionRecency(Protocol):
    async def mentioned_inline_within(self, source_kind: str, source_id: UUID, hours: float) -> bool: ...
    # TurnSurfacing satisfies it.

BarReason = Literal["low_confidence", "irrelevant", "mentioned_recently", "not_novel", "ungrounded"]

@dataclass(frozen=True)
class BarVerdict:
    candidate: PushCandidate
    passed: bool
    reason: BarReason | None

class PushBar:
    def __init__(
        self,
        *,
        embedder: Any,                 # E5 SentenceTransformer wrapper with encode_passage
        nli: NLIClient | None,         # no default; None logs push_bar_grounding_off once
        history: PushHistory,
        mentions: MentionRecency,
        novelty_lookback_hours: float = 48.0,
    ) -> None: ...

    async def screen(
        self, candidates: Sequence[PushCandidate], thresholds: BarThresholds
    ) -> list[BarVerdict]: ...
```

`screen` rules:

1. Read `history.recent_discretionary_bodies(novelty_lookback_hours)` once per call and encode each body once.
2. For each candidate, in input order, the first failing condition names the reason:
   - `low_confidence`: `confidence < thresholds.confidence`;
   - `irrelevant`: `await relevance() < thresholds.relevance` (called only after confidence passes);
   - `mentioned_recently`: `thresholds.inline_cooldown_hours` is set and `mentions.mentioned_inline_within(kind, id, hours)` is true;
   - `not_novel`: the cosine similarity of `body` to any history body is `> novelty_similarity_max`;
   - `ungrounded`: `nli` is set, `labels = await evidence_labels()` (called only here) is not empty, and `nli.grounding_score(claim, labels, scores=await nli.scores([(label, claim) …]))` is `< thresholds.grounding`.
3. An exception inside the mention, novelty or grounding check (including the `evidence_labels` thunk) passes that condition and logs `push_bar_<condition>_check_failed` (research R11). An exception from the `relevance` thunk rejects the candidate as `irrelevant` and logs `push_bar_relevance_check_failed`: an interruption is not sent on a relevance score that could not be computed.

The formulas are the ones in `ze_correlation/push.py:33-88` on main; only their home and inputs change.

## Source protocol (structural; sources do not import ze-priority)

```python
class PushCandidateSource(Protocol):
    source_kind: str
    thresholds: BarThresholds
    dry_run: bool
    async def candidates(self) -> list[PushCandidate]: ...
    async def send(self, candidate: PushCandidate) -> PushOutcome | None: ...
```

### `ze_worldstate.surfacing.LoopSurfacer` (lane `bar`)

```python
class LoopSurfacer:
    source_kind = "loop"
    dry_run = False
    def __init__(self, *, loop_store: LoopStore, graph_store: GraphStore, pool: Any,
                 relevance_model: Any, notifier: Any, settings: LoopPushSettings) -> None: ...
    @property
    def thresholds(self) -> BarThresholds: ...
    async def candidates(self) -> list[PushCandidate]: ...   # drifting loops with a drift_rationale
    async def send(self, candidate: PushCandidate) -> PushOutcome | None:
        # re-reads the loop; None unless still drifting (today's FR-011);
        # notify(LOOP_DRIFT, "Open loop", candidate.body, target_type="open_loop",
        #        target_id=str(id), once_per=candidate.once_per)
        # candidates() builds once_per=OncePer(f"loop:{id}", within=timedelta(days=settings.repush_after_days)),
        # relevance as a thunk over RelevanceModel.build/score on the loop's entity names,
        # evidence_labels as a thunk over the evidence summaries
```

`LoopPushSettings` (`ze_worldstate/bootstrap.py`) gains `repush_after_days: float = 7.0` read from `worldstate.push.repush_after_days`, and a `bar_thresholds()` method mapping the existing keys to `BarThresholds` (see data-model.md). `build_loop_surfacer(stack, relevance_model, notifier, settings)` loses `push_log`, `embedder` and `nli_client`. `passes_push_bar` and `eligible_candidates` are deleted. `format_hedged_mention` stays (TurnSurfacing uses it).

### `ze_correlation.push.CorrelationPushCandidateSource` (lane `bar`)

```python
class CorrelationPushCandidateSource:
    source_kind = "hypothesis"
    def __init__(self, *, hypothesis_store: PostgresHypothesisStore, notifier: Any, settings: Any) -> None: ...
    thresholds: BarThresholds       # from _load_config + nli_config; inline_cooldown_hours=None
    dry_run: bool                   # correlation.push.dry_run
    async def candidates(self) -> list[PushCandidate]: ...   # [] when correlation.push.enabled is false
    async def send(self, candidate: PushCandidate) -> PushOutcome:
        # notify(HYPOTHESIS, ..., once_per=candidate.once_per); if is_sent(outcome): mark_surfaced
        # candidates() builds once_per=OncePer(f"hypothesis:{id}") and wraps relevance and labels in thunks
```

`passes_*`, `_passes_push_bar`, `_passes_novelty`, `_passes_grounding` and `_NOVELTY_LOOKBACK_HOURS` are deleted. `build_correlation_push_candidate_source(stack, notifier, settings)` loses `embedder` and `nli_client`. `PostgresHypothesisStore.list_recently_surfaced_summaries` is deleted.

## `ze_priority/arbitration.py` (lane `bar`)

```python
class AttentionArbitrationJob:
    job_id = "attention_arbitration_sweep"
    def __init__(self, *, priority_view: PriorityView, sources: Sequence[PushCandidateSource],
                 bar: PushBar, notifier: Any) -> None: ...
    async def run(self) -> None: ...
```

`run`:

1. Return when `notifier.remaining_budget() == 0`.
2. For each source: `candidates()`; drop each candidate whose `notifier.on_cooldown(candidate.once_per)` is true, logging `push_candidate_cooling` (`source_kind`, `source_id`), so a cooling loop costs no embedding or NLI (review 2026-10-26, note 2); then `bar.screen(remaining, source.thresholds)`. Log `push_bar_rejected` (`source_kind`, `source_id`, `reason`) per rejection. When `source.dry_run`, log `push_candidate_dry_run` per passing candidate and drop them.
3. Rank the passing candidates with `priority_view.rank_subset([PriorityCandidateRef(c.source_kind, c.entity) …])`.
4. In ranked order, `send` through the owning source. Stop on `is_sent(outcome)` or `suppressed_budget`; otherwise log `attention_arbitration_candidate_skipped` with the outcome (`deduped`, `failed`, `None`) and try the next.

`loop_push` and the `LoopPushSettings` import go: the wiring includes the loop source only when `worldstate.push.enabled` is true.

## `ze_priority/turn.py` and `ze_priority/surfacing_memory.py` (lane `conv`)

```python
class SurfacingMemory(Protocol):
    async def record(self, kind: Literal["inline", "offer"], source_kind: str, source_ids: Sequence[UUID]) -> None: ...
    async def recorded_within(self, kind: Literal["inline", "offer"], source_kind: str, source_id: UUID, hours: float) -> bool: ...

class PostgresSurfacingMemory:   # implements SurfacingMemory over surfacing_memory (zpri002)
    def __init__(self, pool: asyncpg.Pool) -> None: ...

class TurnSurfacing:
    def __init__(self, priority_view: PriorityView, graph_store: Any, loop_store: Any,
                 embedder: Any, memory: SurfacingMemory,
                 open_query_detector: OpenQueryDetector | None = None) -> None: ...
    async def mentioned_inline_within(self, source_kind: str, source_id: UUID, hours: float) -> bool: ...
    # other public methods unchanged
```

- `inline_mentions` records loop mentions with `memory.record("inline", "loop", ids)`.
- `resume_loop_offers` checks `memory.recorded_within("offer", "loop", id, OFFER_COOLDOWN_HOURS)` and records offered ids with `memory.record("offer", "loop", ids)`. A read error returns `[]` (today's rule).
- `OFFER_EVENT_PREFIX` and the `push_log` argument are deleted.
