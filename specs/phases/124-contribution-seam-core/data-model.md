# Data Model: Contribution Seam Core

## New types — `core/ze-plugin/ze_plugin/contribution.py`

### `SourceFunction` (StrEnum)

Doctrine-mandated closed set (the seven cognitive functions), per Principle III's
closed-enum carve-out. See research.md §3.

```
PERCEPTION, MEMORY, EXECUTIVE, SOCIAL_COGNITION, REFLECTION, ACTION, GOVERNANCE
```

### `TargetFace` (StrEnum)

Doctrine-mandated closed set (the four world-state faces). See research.md §3.

```
SELF, USER, WORLD, ACTIVE_CONCERNS
```

### `EvidenceRef` (dataclass)

```python
@dataclass
class EvidenceRef:
    kind: Literal["fact", "episode", "signal"]
    id: UUID
```

Shared shape for `Contribution.evidence`; superset of `ze_worldstate.types.EvidenceRef`'s
`evidence_type: "fact" | "episode"` (worldstate never needs `"signal"` but the shared type
accepts it for correlation's use). `ze_correlation.types.EvidenceRef` keeps its richer
existing shape (label, external_ref, origin, timestamps — used for hypothesis display) and
is **not** replaced; correlation constructs a `contribution.EvidenceRef` from its own
`EvidenceRef.kind`/`.id` when submitting to the seam (a lossy, one-directional projection,
acceptable because the seam only needs kind+id to check existence, not display metadata).

### `Contribution` (dataclass)

```python
@dataclass
class Contribution:
    claim_kind: ClaimKind            # ze_agents.claims
    provenance: Provenance           # ze_agents.claims
    confidence: Confidence           # ze_agents.claims
    target_face: TargetFace
    source_function: SourceFunction
    evidence: list[EvidenceRef] = field(default_factory=list)
```

**Validation rules** (enforced by `validate_and_submit()`, not by `__post_init__` — construction
itself is never rejected, only submission; this matches FR-009's "not a precedence-ordered
arbiter," i.e. validation is a single-contribution gate, not object-level invariants):

- `claim_kind` MUST be a member of `_LICENSE[source_function]` (FR-007).
- If `claim_kind in {INFERENCE, SUSPICION}`, `evidence` MUST be non-empty (FR-011).
- Every `EvidenceRef` in `evidence` MUST resolve via the caller-supplied existence-check
  callable matching its `kind` (FR-011, research.md §8).

### `validate_and_submit()` (function, not a class — no new persisted queue, per Assumptions)

```python
async def validate_and_submit(
    contribution: Contribution,
    write: Callable[[], Awaitable[T]],
    *,
    check_fact_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    check_episode_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    check_signal_exists: Callable[[UUID], Awaitable[bool]] | None = None,
) -> T:
    ...
```

Validates licensing + evidence, logs+raises on rejection (research.md §9/§10), otherwise
awaits and returns `write()` unchanged — `write` is the existing store call
(`loop_store.create`, `dream_store.save_artifact`, `hypothesis_store.save`), never replaced,
only gated (Assumptions: "a guard function/wrapper, not a new persisted queue").

### Error types — `core/ze-agents/ze_agents/errors.py`

`ContributionError(ZeCoreError)` → `UnlicensedClaimKindError`, `MissingEvidenceError`,
`DanglingEvidenceError` (research.md §10).

## Retrofitted types

### `Signal` (`core/ze-memory/ze_memory/types.py`) — modified

Adds one field:

```python
provenance: Provenance   # ze_agents.claims — NEW (FR-002)
```

`source: str` (plugin key), `claim_kind: ClaimKind`, `confidence: float`, `magnitude: float`
are unchanged. A new method (or free function in a new `ze_memory/contribution.py`) converts a
`Signal` to a `contribution.Contribution`:

```python
def signal_to_contribution(signal: Signal) -> Contribution:
    return Contribution(
        claim_kind=ClaimKind.FACT,           # perception's sole license, always — FR-003
        provenance=signal.provenance,
        confidence=Confidence(
            value=signal.confidence,
            decay_profile=DecayProfile.TIME_LINEAR,   # research.md §12
        ),
        target_face=TargetFace.WORLD,        # perception always targets world-state facts
        source_function=SourceFunction.PERCEPTION,
        evidence=[],                          # facts cite nothing — perception is the origin
    )
```

`ze_memory.retriever.PostgresRetriever.ingest_signal()` — the real write path that persists a
`Signal` to `memory_signals` — wraps its insert in `validate_and_submit(contribution, write=...)`
using this conversion (FR-003 amended, Edge Case 1). `evidence=[]` means no existence-check
callables are needed at this call site (FR-011's non-empty rule only applies to
`INFERENCE`/`SUSPICION`, and perception is licensed for `FACT` only).

### `OpenLoop` (`core/ze-worldstate/ze_worldstate/types.py`) — unchanged shape

No new fields (already has `claim_kind`, `confidence` from Phase 111's `zw001`/claim-topology
retrofit). `provenance: str` (inflow) stays exactly as-is (FR-004, research.md §5). A new
conversion function in `ze_worldstate/contribution.py`:

```python
def loop_to_contribution(
    loop: OpenLoop, evidence: list[EvidenceRef] | None = None
) -> Contribution:
    return Contribution(
        claim_kind=loop.claim_kind,
        provenance=_INFLOW_TO_EPISTEMIC[loop.provenance],   # research.md §5 mapping table
        confidence=Confidence(
            value=loop.confidence,
            decay_profile=DecayProfile.TIME_LINEAR,   # research.md §12
        ),
        target_face=TargetFace.ACTIVE_CONCERNS,
        source_function=SourceFunction.EXECUTIVE,
        evidence=evidence or [],
    )
```

`extraction.py` has two `loop_store.create()` call sites, both wrapped in `validate_and_submit()`
(FR-004 amended, Edge Case 1, research.md §5):

- `_create_declared_loop` — always `claim_kind=PRIORITY`, `evidence=[]` (FR-011's non-empty rule
  doesn't apply to `PRIORITY`), so no existence-check callables are needed here.
- `propose_loop_candidates`'s gated/non-declared path — `claim_kind=SUSPICION`, so `evidence`
  MUST be non-empty; this call site already receives `evidence_refs:
  list[ze_worldstate.types.EvidenceRef]` as a parameter (used for `_link_evidence_and_entities`)
  — converted 1:1 to `contribution.EvidenceRef(kind=..., id=...)` and passed through, with real
  `check_fact_exists`/`check_episode_exists` callables wired the same way as the dream/correlation
  call sites (research.md §8).

### `DreamArtifact` staging (`core/ze-memory/ze_memory/dream/`) — write-path change only

No dataclass field changes. `dream_pass.py`'s four `save_artifact()` call sites gain a
`claim_kind=ClaimKind.INFERENCE` argument (always — dream never emits `FACT` or `SUSPICION`,
per FR-005) and route through `validate_and_submit()` before the existing
`dream_store.save_artifact(...)` call. `evidence` is built from each artifact's existing
`source_fact_ids`/`source_episode_ids` lists, converted to `contribution.EvidenceRef`.
`confidence=Confidence(value=0.5, decay_profile=DecayProfile.TIME_LINEAR)` (research.md §11 —
a fixed neutral placeholder; the promotion gate's own scoring, unchanged by this feature, is what
actually determines promotion, not this value). `target_face=TargetFace.SELF` (research.md §13).

### `Hypothesis` save (`core/ze-correlation/`) — write-path change only

No dataclass field changes (`Hypothesis.claim_kind` already exists, always `SUSPICION` today).
`engine.py`'s `hypothesis_store.save(hypothesis)` call is wrapped in `validate_and_submit()`;
`evidence` is built from `Hypothesis.evidence: list[EvidenceRef]` (correlation's own richer
type), projected down to `contribution.EvidenceRef(kind=e.kind, id=e.id)` per evidence item.
`confidence=Confidence(value=hypothesis.confidence, decay_profile=DecayProfile.TIME_LINEAR)` —
unlike dream, `Hypothesis` already carries a real LLM self-rated `confidence: float` at save
time, so (unlike dream's staging-time gap, research.md §11) there is no missing-value problem
here; `TIME_LINEAR` matches the profile `ze_correlation/jobs/hypothesis_decay.py`'s existing
`HypothesisDecayJob` already uses to age `Hypothesis.confidence` post-save (confirmed by reading
that file — it calls `decay(hypothesis.confidence, DecayProfile.TIME_LINEAR, elapsed_days=...)`),
so the `Contribution`'s decay profile stays consistent with the value's actual subsequent
lifecycle rather than introducing a second, different decay characterization of the same number.
`target_face=TargetFace.SELF` (research.md §13).

## New migration

`core/ze-memory/ze_memory/migrations/versions/zm018_signal_provenance.py` (next free `zm`
revision after `zm017`) — adds `provenance TEXT NOT NULL DEFAULT 'synthesized'` to
`memory_signals`, then drops the default (new rows must set it explicitly going forward) per the
zm017 precedent (research.md §7).

## State / relationships

No new state machine. `Contribution` is constructed, validated, and discarded per call — it is
never itself persisted (Assumptions). The existing state machines it feeds
(`ArtifactStatus`, `LoopState`, `Hypothesis` — no status field) are unchanged.
