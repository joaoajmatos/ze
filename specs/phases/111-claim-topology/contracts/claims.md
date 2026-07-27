# Contracts: Claim Topology

This feature adds no REST endpoints (spec Assumptions: "entirely backend/type-layer; no web UI
surface is expected to change"). Its interfaces are new/changed Python module surfaces four
other packages depend on. Each is documented below as the stable contract other code depends on.

## 1. `ze_agents.claims` — the new shared vocabulary (new inter-package surface)

The contract every other package in this feature imports. Stable from the moment it lands —
`ze-worldstate`, `ze-correlation`, `ze-memory` all consume it directly. `Provenance` is
deliberately closed at exactly four values — see §7 for why inflow-channel values are not here.

```python
class ClaimKind(StrEnum):
    IDENTITY = "identity"
    FACT = "fact"
    INFERENCE = "inference"
    SUSPICION = "suspicion"
    PRIORITY = "priority"

class Provenance(StrEnum):
    GRAPH_RECALL = "graph_recall"
    LIVE_SEARCH = "live_search"
    PROMPT_SUPPLIED = "prompt_supplied"
    SYNTHESIZED = "synthesized"

class DecayProfile(StrEnum):
    EVIDENCE_WEIGHTED = "evidence_weighted"
    TIME_LINEAR = "time_linear"

@dataclass
class Confidence:
    value: float
    decay_profile: DecayProfile

def decay(
    value: float,
    decay_profile: DecayProfile,
    *,
    remaining_evidence: int | None = None,
    total_evidence: int | None = None,
    elapsed_days: float | None = None,
) -> float: ...
```

- `decay()` raises `ValueError` (a typed `ZeError` subclass per `CLAUDE.md` convention — not a
  bare `ValueError`) if the caller omits the parameters its `decay_profile` requires
  (`EVIDENCE_WEIGHTED` needs `remaining_evidence`/`total_evidence`; `TIME_LINEAR` needs
  `elapsed_days`), so a caller can never silently get a no-op decay.
- `Provenance` MUST NEVER gain a member naming a specific plugin, channel, or inflow mechanism
  (FR-002; `specs/arch/plugin-domain-vocabulary.md`). Any future PR proposing to add one is a
  constitution violation, not a routine enum extension — it belongs in the caller's own
  plugin-owned string instead.
- Values are plain floats in / floats out — callers own persistence (this module has no store,
  no async, no I/O), consistent with `ze_agents.nli`'s existing footprint as a dependency-free
  contract module (research.md §8).

## 2. `ze_worldstate.types` — `LoopClaimKind` re-exported, `LoopProvenance` reshaped

`LoopClaimKind` remains importable exactly as before (FR-006):

```python
from ze_worldstate.types import LoopClaimKind  # still works, unchanged values
```

Internally: `LoopClaimKind = ClaimKind` (alias of `ze_agents.claims`'s enum).

`LoopProvenance` changes shape — closed `StrEnum` → plain string-constant namespace (FR-003):

```python
from ze_worldstate.types import LoopProvenance

LoopProvenance.CONVERSATION   # "conversation" — still works, same value
LoopProvenance.USER_DECLARED  # "user_declared" — still works, same value
LoopProvenance.INGESTION      # "ingestion" — still works, same value
LoopProvenance.EMAIL          # REMOVED — was never pattern-matched (research.md §3); plugins
                               # now pass the literal string "email" directly
LoopProvenance.CALENDAR       # REMOVED — same as above, for "calendar"
LoopProvenance("anything")    # REMOVED — no more enum-membership coercion/validation
```

Every existing `ze-worldstate` call site and test using `LoopProvenance.CONVERSATION`/
`LoopProvenance.USER_DECLARED` (production code and eleven test files, per research.md §3's
audit) continues to work with no changes — the contract is that those two symbols keep resolving
to the same string values. Code that constructed a loop with `LoopProvenance.EMAIL`/`.CALENDAR`
does not exist anywhere in this repo today (confirmed by audit) — none needs migrating.

## 3. `ze_worldstate.extraction.propose_loop_candidates` — validation removed, signature unchanged

```python
async def propose_loop_candidates(
    text: str,
    provenance: str,       # UNCHANGED signature — was already str at this boundary
    evidence_refs: list[EvidenceRef],
    llm_client: LLMClient,
    embedder: Any,
    loop_store: LoopStore,
    entity_resolver: Any,
    *,
    graph_store: GraphStore | None = None,
    model: str = DEFAULT_EXTRACTION_MODEL,
) -> list[OpenLoop]: ...
```

Behavior change (FR-003): the internal `prov = LoopProvenance(provenance)` coercion — which
raised `ValueError` for any string not in the old 5-value whitelist — is removed. The function
now uses the incoming string directly; its two special-case comparisons
(`provenance == LoopProvenance.CONVERSATION` triggering the relabel-to-`user_declared` path,
`provenance == LoopProvenance.USER_DECLARED` triggering the declared-loop fast path) are
unaffected string comparisons. A caller passing an unrecognized string (e.g. a future plugin's
own inflow channel) now succeeds instead of raising — this is the contract's actual behavior
change, and it's additive (previously-rejected calls now succeed), not breaking.

## 4. `ze_worldstate.decay.cascade_from_evidence` — unchanged signature, internal call swapped

```python
async def cascade_from_evidence(
    evidence_type: str,
    evidence_id: UUID,
    loop_store: LoopStore,
) -> list[OpenLoop]: ...
```

Signature, return shape, logging events, and state-transition behavior are all unchanged
(FR-018: no gating/behavior change for `OpenLoop`). The only internal change is that the
confidence-arithmetic line now calls `ze_agents.claims.decay(..., decay_profile=
DecayProfile.EVIDENCE_WEIGHTED, remaining_evidence=..., total_evidence=...)` instead of its own
inline expression (research.md §5).

## 5. `ze_correlation.types.Hypothesis` / `EvidenceRef` — additive and type-widening changes

```python
@dataclass
class Hypothesis:
    ...
    claim_kind: ClaimKind  # NEW — INFERENCE | SUSPICION only, never FACT

@dataclass
class EvidenceRef:
    ...
    origin: Provenance  # WAS: Literal["graph_recall", "live_search", "prompt_supplied"]
                         # confirmed correct fit for the doctrine-closed enum (research.md §4)
```

`PostgresHypothesisStore.save`/`get`/`_row_to_hypothesis` (`ze_correlation/store.py`) gain the
new `claim_kind` column read/write; existing columns and query shapes are unchanged.

## 6. New `HypothesisDecayJob` — new scheduled job in `ze-correlation`

Registered the same way `ze-correlation`'s existing `CorrelationJob` is (`@proactive_job`,
`ze_proactive.job`), per the clarification answer: standalone job, own cadence, not folded into
`CorrelationJob`/`CorrelationPushConsumer`.

```python
@proactive_job
class HypothesisDecayJob:
    job_id = "hypothesis_decay_sweep"

    def __init__(self, hypothesis_store: PostgresHypothesisStore) -> None: ...

    async def run(self) -> None: ...
```

- Selects hypotheses with no new corroborating evidence since a `TIME_LINEAR`-window elapsed
  (mirrors `memory_facts`' 30-day window, per clarification), calls
  `ze_agents.claims.decay(..., decay_profile=DecayProfile.TIME_LINEAR, elapsed_days=...)`, and
  persists the updated `confidence` via a new `PostgresHypothesisStore.set_confidence` method
  (mirrors `LoopStore.set_confidence`'s existing shape) — with the same
  `hypothesis_confidence_decayed` structured-log auditability `OpenLoop`'s decay path already
  has (Acceptance Scenario 1).
- Registered in `ze_correlation`'s job-registration fan-out alongside `CorrelationJob`
  (mirrors how `ze-worldstate` registers `StaleSuspicionJob`/`DriftSweepJob`/`PushSweepJob`
  independently rather than folding them into one job).

## 7. `ze_memory.types.Signal` — additive fields (corrected location, research.md §1)

```python
@dataclass
class Signal:
    ...
    claim_kind: ClaimKind  # NEW — always FACT
    confidence: float      # NEW — required; distinct from existing `magnitude`
```

No `provenance`/inflow field is added to `Signal` in this feature — `Signal.source: str`
(existing) already identifies the producing plugin/source key, the same plugin-owned-string
pattern `OpenLoop.provenance` now follows (§2). This is why inflow-channel values were never a
good fit for a core `Provenance` enum in the first place: the codebase already had a working
plugin-owned-string precedent (`Signal.source`) before this feature started.

`SignalSource` Protocol (`ze_plugin/signals.py`) is unchanged (FR-014) — it still returns
`list[Signal]`; the four implementers (`ze-calendar`, `ze-finance`, `ze-messenger`, `ze-news`)
each add `claim_kind=ClaimKind.FACT` and a real `confidence=...` value at their existing
`Signal(...)` construction call sites.

## 8. `ze_proactive.staleness.is_stale` — new shared helper (new inter-package surface)

```python
def is_stale(timestamp: datetime, window_days: int, *, now: datetime | None = None) -> bool: ...
```

Consumed by `ze_worldstate.jobs.stale_suspicion.StaleSuspicionJob`,
`ze_worldstate.jobs.drift_sweep` (via a widened `LoopStore.list_drift_candidates` that drops its
own `drift_deadline <= now()` SQL predicate and filters via this helper instead, per
research.md §7), and `ze_automation.jobs.stuck_goals.StuckGoalJob` (via a similarly widened
`GoalStore.list_stuck`, keeping its separate `alert_cooldown_days` SQL suppression untouched).
Each caller retains its own state-transition and window-configuration logic — this function
only answers the one shared "is this past its cutoff" question (FR-015).

## 9. Migration contracts

| Migration | Package | Chain | Adds |
|---|---|---|---|
| new `zcor00N` | `core/ze-correlation` | `zcor` | `correlation_hypothesis.claim_kind TEXT NOT NULL`, backfilled `'inference'` |
| new `zm0NN` | `core/ze-memory` | `zm` | `memory_facts.claim_kind TEXT NOT NULL`, backfilled per FR-010's rule |

Both use the standard `ALTER ... ADD COLUMN` (nullable) → `UPDATE ... SET` (backfill) →
`ALTER ... SET NOT NULL` three-step sequence for adding a required column to a non-empty table,
so no row is ever left without a `claim_kind` (FR-016, SC-006). No migration touches
`open_loops.provenance` — its database column stays `TEXT`; only its Python-side type
annotation changes (§2).
</content>
