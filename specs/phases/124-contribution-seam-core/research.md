# Research: Contribution Seam Core

**Input**: `specs/phases/124-contribution-seam-core/spec.md`, `specs/arch/contribution-seam.md`,
`specs/arch/claim-topology.md`, `specs/arch/ze-doctrine.md`

No `NEEDS CLARIFICATION` markers remain in the spec (resolved in `/speckit-clarify`). This
document resolves implementation-level unknowns surfaced while reading the actual producer code.

## 1. Where `Contribution` lives

**Decision**: New `core/ze-plugin/ze_plugin/contribution.py` — `Contribution` dataclass, the
`ContributionRejectedError` hierarchy, and `validate_and_submit()`, the shared guard function.

**Rationale**: `contribution-seam.md` names `ze-plugin` as the seam's home ("the natural home
for the `Contribution` contract"). `ze-plugin` has no `types.py` today (`plugin.py`,
`signals.py`, `registry.py`, `integration.py`, `webhook.py`, `ui.py`, `api_auth.py`,
`bootstrap.py`) — this is the first dataclass-only module in the package, matching the
`types.py`-naming convention used everywhere else in the repo (CLAUDE.md).

**Alternatives considered**: `ze-agents` (rejected — `Contribution` is not agent-execution API,
it is a cross-plugin write-path contract, and `ze-plugin` already depends on `ze-agents.claims`
transitively via nothing today, so this establishes a clean new import, not a cycle).
`ze-core` (rejected — `ze-core` is engine-internal and never a plugin dependency per the
dependency graph in `CLAUDE.md`; `Contribution` must be importable from `core/ze-memory`,
`core/ze-worldstate`, and `core/ze-correlation`, none of which may depend on `ze-core`).

## 2. Licensing table shape

**Decision**: A plain `dict[str, frozenset[ClaimKind]]` module-level constant,
`_LICENSE: dict[str, frozenset[ClaimKind]]`, keyed by `source_function` string (not a new core
enum — see below), in `contribution.py` itself.

**Rationale**: FR-007 requires the check to be general-purpose, keyed on `source_function`.
The seven cognitive functions (perception, memory, executive, social cognition, reflection,
action, governance) are a *doctrine-mandated closed set* — per `CLAUDE.md`'s Principle III
carve-out ("a value belongs in a core-owned closed enum only if a governing doctrine/ADR
mandates that exact closed set"), `source_function` **is** such a value: `ze-doctrine.md`
names exactly these seven functions and their claim-kind licenses. This is the same reasoning
`ClaimKind`/`Provenance` used in Phase 111 — it is doctrine vocabulary, not plugin vocabulary.

This feature only wires two rows of the table for real (`perception → {FACT}`,
`reflection → {INFERENCE, SUSPICION}`); the other five functions exist in the enum for
forward-compatibility (`executive` gets the full range OpenLoop already uses:
`IDENTITY, FACT, INFERENCE, SUSPICION, PRIORITY`, matching Edge Case 4) but have no producer yet.

**Alternatives considered**: A DB-backed configurable table (rejected — YAGNI; the doctrine's
own licensing table is fixed, not an operator-tunable setting, and Assumptions explicitly rule
out new persisted state beyond the one migration). A per-producer local check (rejected — this
is exactly the duplication FR-007 forbids: "one licensing check, not two independent
reimplementations").

## 3. `source_function` and `target_face` enum values

**Decision**: Two new `StrEnum`s in `ze_plugin/contribution.py`:

```python
class SourceFunction(StrEnum):
    PERCEPTION = "perception"
    MEMORY = "memory"
    EXECUTIVE = "executive"
    SOCIAL_COGNITION = "social_cognition"
    REFLECTION = "reflection"
    ACTION = "action"
    GOVERNANCE = "governance"

class TargetFace(StrEnum):
    SELF = "self"
    USER = "user"
    WORLD = "world"
    ACTIVE_CONCERNS = "active_concerns"
```

**Rationale**: Directly from the doctrine's four world-state faces and seven cognitive
functions (Assumptions section of the spec). Both are closed sets mandated by
`specs/arch/ze-doctrine.md`, so — per the same Principle III carve-out as §2 — they belong in
`ze-plugin` as core-owned enums, not as plugin-supplied strings.

## 4. `Signal.provenance` — new column, not a derived value

**Decision**: `Signal` gains a real `provenance: Provenance` field (`ze_agents.claims`).
Existing `Signal.source: str` (plugin key, e.g. `"news"`) is untouched — it is plugin-domain
vocabulary per `specs/arch/plugin-domain-vocabulary.md`, confirmed by FR-002. A new Alembic
migration on the `zm` chain adds the `provenance` column to `memory_signals`
(nullable at first with a backfill default, since existing rows predate the field — see §7).

Every existing `SignalSource` implementation must be updated to populate `provenance` (most
will use `Provenance.LIVE_SEARCH` for polled external sources like `NewsSignalSource`, or
`Provenance.GRAPH_RECALL` for `CalendarSignalSource` reading from the user's own calendar data
already in the graph — this per-producer call-site choice is an implementation-phase decision,
not a spec ambiguity: it follows directly from what each `SignalSource` actually does).

**Rationale**: FR-002 is explicit. `Signal.confidence`/`Signal.claim_kind` already exist from
Phase 111's `zm017`; `provenance` is the one missing field.

## 5. `OpenLoop.provenance` is NOT `ze_agents.claims.Provenance` — a mapping is required

**Decision**: `OpenLoop.provenance: str` (the `LoopProvenance` namespace —
`conversation` / `ingestion` / `user_declared`) is **inflow vocabulary**, analogous to
`Signal.source`, not epistemic `Provenance`. It stays exactly as-is (FR-004 explicitly keeps
OpenLoop's mechanics unchanged). When `extraction.py` wraps a produced `OpenLoop` as a
`Contribution`, `Contribution.provenance` (the epistemic field) is derived via a small mapping,
not copied:

| `OpenLoop.provenance` (inflow) | → | `Contribution.provenance` (epistemic) |
|---|---|---|
| `user_declared` (explicit self-declaration, `_create_declared_loop`) | → | `PROMPT_SUPPLIED` |
| `conversation` (LLM-inferred via the relevance gate, not explicitly declared) | → | `SYNTHESIZED` |
| `ingestion` (email/calendar extraction) | → | `SYNTHESIZED` |

**Rationale**: This mirrors exactly how `Signal.source` (plugin key) and the new
`Signal.provenance` (epistemic) coexist per §4/FR-002 — the spec establishes this pattern for
`Signal` but doesn't need to restate it for `OpenLoop` because `OpenLoop.provenance` already
existed pre-feature as inflow vocabulary (`zw001`, Phase 109) and was never epistemic
`Provenance` to begin with. `user_declared` is the user directly stating the commitment in the
conversation turn (`prompt_supplied`, matching the doctrine's "directly from the user" case);
`conversation`/`ingestion` both pass through the LLM extraction gate (`_run_extraction_gate`),
which is model-synthesized inference over raw text, matching `SYNTHESIZED`.

**Alternatives considered**: Widening `OpenLoop.provenance`'s type to `Provenance` directly
(rejected — would collapse two distinct concepts, inflow channel vs. epistemic origin, into one
field, the same regression claim-topology's Phase 111 mapping pass explicitly rejected for
`Signal.magnitude`/`confidence`; also FR-004 forbids changing OpenLoop's existing *matching and
call-signature* mechanics).

**Also resolved here**: per FR-004 (amended) and Edge Case 1, `extraction.py`'s two
`loop_store.create()` call sites route through `validate_and_submit()` using
`loop_to_contribution()`, so a malformed `OpenLoop` (wrong `claim_kind` for `EXECUTIVE`'s
license) is rejected the same general way a mistagged reflection contribution is — this is a thin
gate in front of the existing call, not a rewrite of `extraction.py`'s matching/dedup logic.
`extraction.py` actually has two distinct call sites with two distinct `claim_kind`s:
`_create_declared_loop` always tags `PRIORITY` (no evidence required, FR-011's non-empty rule
only bites `INFERENCE`/`SUSPICION`); the non-declared/gated path in `propose_loop_candidates`
(line ~266) tags `SUSPICION` and *does* require non-empty evidence — that call site already
receives `evidence_refs: list[ze_worldstate.types.EvidenceRef]` as a parameter (used today for
`_link_evidence_and_entities`), which the wiring task converts to
`contribution.EvidenceRef(kind=..., id=...)` and passes to `validate_and_submit()`, wiring real
`check_fact_exists`/`check_episode_exists` callables the same way `dream_pass.py`/`engine.py` do
(research.md §8).

## 6. The dream pipeline's `HINDSIGHT_FACT` artifact type — naming trap

**Finding**: `ArtifactType.HINDSIGHT_FACT` (`ze_memory/dream/types.py`) is an existing dream
artifact type whose *name* contains "fact," but it is a reconstructed/synthesized inference
about a past event (hindsight reasoning), not a directly observed fact. When `dream_pass.py`'s
four `save_artifact()` call sites (`SYNTHESIZED_INSIGHT`, `SYNTHESIZED_PROCEDURE`,
`HINDSIGHT_FACT`, `PLAN_STRESS_TEST`) are migrated to route through
`validate_and_submit()`, **all four must tag `claim_kind=INFERENCE`** (never `FACT`) —
`HINDSIGHT_FACT` is an `artifact_type` label, unrelated to `claim_kind`. This is precisely the
failure mode FR-005/User Story 2 exists to catch mechanically: a plausible-looking artifact type
name must never leak into the claim-kind tag. Flagging this explicitly in `tasks.md` and a
dedicated test (`test_hindsight_fact_is_never_claim_kind_fact`) so the naming coincidence can't
silently regress.

**Rationale**: Confirmed by reading `dream_pass.py`'s four `save_artifact()` call sites — none
currently pass a `claim_kind` at all (the field doesn't exist yet at the staging layer;
`claim_kind` only appears downstream in `promoter.py` at the point of promotion to
`memory_facts`). This feature adds `claim_kind` as a required argument to the new staging
write path, sourced from the artifact-generation call site, not from `artifact_type`.

## 7. `provenance` migration backfill for existing `Signal` / `Contribution` rows

**Decision**: `Signal.provenance` is added via `core/ze-memory/ze_memory/migrations/versions/
zm018_signal_provenance.py` (the next free `zm` revision after `zm017`) as `NOT NULL` with a
one-time backfill default of `Provenance.SYNTHESIZED` for any pre-existing `memory_signals` rows
(they predate honest per-signal provenance tracking and were, in practice, model-processed
before storage) — matching the migration precedent set by Phase 111's `zm017`, which backfilled
`claim_kind`/`confidence` onto `memory_signals`/`memory_facts`/`open_loops`/`hypotheses` the
same way.

**Rationale**: Assumptions section confirms "No new Alembic migrations are required beyond
`Signal`'s `provenance` column." A nullable column would leave a permanent escape hatch from the
type system the doctrine is trying to close; backfilling matches the zm017 precedent instead of
introducing a new nullable-forever pattern.

## 8. Evidence reference validation dispatch (Clarification Q2)

**Decision**: `Contribution.evidence: list[EvidenceRef]` where `EvidenceRef` is a small
dataclass `(kind: Literal["fact", "episode", "signal"], id: UUID)` — reusing
`ze_correlation.types.EvidenceRef`'s existing `kind` vocabulary (already a superset of what
`ze_worldstate.types.EvidenceRef` calls `evidence_type: "fact" | "episode"`). `validate_and_submit()`
takes injected lookup callables — `check_fact_exists`, `check_episode_exists`,
`check_signal_exists` — one per kind, so the guard function itself has no direct store
dependency (keeps `ze-plugin` free of a `ze-memory`/`ze-correlation` import cycle) and each
caller wires in whichever lookups its own store already exposes.

**Rationale**: Directly implements the clarify-session decision (Q2). Dependency-injecting the
existence checks (rather than `ze-plugin` importing `ze-memory`'s pool directly) preserves the
Principle III dependency direction — `ze-plugin` has no domain knowledge and must not depend on
`ze-memory` or `ze-correlation`.

## 9. Rejection logging (Clarification Q1)

**Decision**: `validate_and_submit()` calls `get_logger(__name__).warning(...)` with a
structured event name (`contribution_rejected`) and fields `source_function`, `claim_kind`,
`reason` (`"unlicensed_claim_kind"` | `"missing_evidence"` | `"dangling_evidence"`) immediately
before raising the typed error — matching the existing `log.warning(...)` pattern already used
at rejection points elsewhere in the codebase (e.g. `loop_extraction_gate_failed` in
`extraction.py`, `correlation_materialize_facts_failed` in `engine.py`).

## 10. Error types

**Decision**: New errors in `ze_agents/errors.py` (the canonical `ZeError` hierarchy, per
CLAUDE.md — "Raise from `ze_api/errors.py` or `ze_sdk/errors.py`... always use a typed subclass
of `ZeError`" and `ze_agents.errors.ZeCoreError` is the actual base class all of these alias):

```python
class ContributionError(ZeCoreError):
    """Base class for contribution-seam write-path errors."""

class UnlicensedClaimKindError(ContributionError):
    """A contribution's claim_kind is not licensed for its source_function."""

class MissingEvidenceError(ContributionError):
    """An INFERENCE/SUSPICION contribution has no evidence."""

class DanglingEvidenceError(ContributionError):
    """A cited evidence reference does not exist."""
```

**Rationale**: `ze_agents.errors` already hosts every domain error family (`GoalError`,
`WorkflowError`, `MemoryError`, ...); `ContributionError` continues that pattern. `ze-plugin`
already may depend on `ze-agents` (no new dependency edge — `ze_agents.claims` is already
imported transitively through `Contribution`'s own fields).

## 11. `Contribution.confidence` source for dream-pipeline submissions

**Finding**: `DreamArtifact` (`ze_memory/dream/types.py`) carries no confidence-like value at
staging time — `faithfulness_score`/`novelty_score` are computed later, downstream, by the
promotion gate (`gates.py`/`promoter.py`), confirmed by grep: `dream_pass.py` has zero matches
for `confidence`. `Contribution.confidence` is a required field (FR-001), so the four
`save_artifact()` call sites migrated by FR-005 need a defined source.

**Decision**: Use a fixed neutral value, `Confidence(value=0.5, decay_profile=DecayProfile.TIME_LINEAR)`,
for every dream-pipeline `Contribution` at staging time, for all four artifact types
(`SYNTHESIZED_INSIGHT`, `SYNTHESIZED_PROCEDURE`, `HINDSIGHT_FACT`, `PLAN_STRESS_TEST`).

**Rationale**: The seam's write path (`validate_and_submit()`) validates *shape and license*,
not epistemic strength — FR-010 is explicit that the seam does not replace or duplicate the
existing promotion gate's NLI/critic scoring. At staging time, an artifact has not yet been
faithfulness/novelty-scored, so any confidence value assigned here is necessarily provisional;
`0.5` (the studied midpoint, not "confident" or "unconfident") signals exactly that — "unverified,
pending promotion-gate review" — without inventing a derived score from staging-only fields
(`support_count`, `distinct_session_count`) that the promotion gate itself, not the seam, is
responsible for turning into a real confidence value once an artifact is promoted to
`memory_facts`. This value is never read by anything downstream of `validate_and_submit()` — the
promotion gate's own scoring (`faithfulness_score`, `novelty_score`, critic verdicts) remains
the sole basis for promotion decisions, unchanged by this feature (FR-010).

**Alternatives considered**: Deriving a value from `support_count`/`distinct_session_count`
(rejected — would encode a scoring heuristic in the seam's write-path guard, which per FR-010 is
explicitly the promotion gate's job, not the seam's; also no such heuristic exists today to
port). Making `Contribution.confidence` optional for reflection (rejected — `Contribution` is
one shared shape across all producers per SC-003; a nullable field for one producer only would
be exactly the "producer-local bespoke convention" the feature exists to eliminate).

## 12. `decay_profile` choice for `Signal`/`OpenLoop`/`Hypothesis`-derived contributions

**Decision**: `DecayProfile.TIME_LINEAR` everywhere in this feature — `signal_to_contribution()`,
`loop_to_contribution()`, and the correlation engine's `Hypothesis`→`Contribution` conversion.

**Rationale**: `EVIDENCE_WEIGHTED` decay (`ze_agents.claims.decay()`) requires
`remaining_evidence`/`total_evidence` counts — neither `Signal` nor `OpenLoop` tracks an
evidence-corroboration count today (`Signal.magnitude` is relevance, not an evidence count;
`OpenLoop`'s evidence lives in a separate `loop_evidence`-style link table, not a count on the
loop itself). `TIME_LINEAR` only needs `elapsed_days`, computable from each type's existing
`occurred_at`/`created_at` timestamp, matching how both types' confidence values behave today
(a float that isn't actively re-weighted by evidence count, just aged). For `Hypothesis`, this
also matches its *existing* real decay treatment — confirmed by reading
`ze_correlation/jobs/hypothesis_decay.py`: `HypothesisDecayJob` already calls
`decay(hypothesis.confidence, DecayProfile.TIME_LINEAR, elapsed_days=...)` on a sweep, so tagging
the `Contribution` wrapper with the same profile keeps it consistent with how the value actually
ages post-save, rather than asserting a different (and unused) characterization at the seam.

## 13. `target_face` for reflection producers (dream, correlation)

**Decision**: `TargetFace.SELF` for both the dream pipeline's and the correlation engine's
contributions.

**Rationale**: The doctrine's four faces split by *whose* claim it is, not by which entities the
claim happens to mention: `self` is Ze's own synthesized understanding/reasoning, `user` is
claims about the user's own life, `world` is claims about external entities/events, and
`active_concerns` is the executive layer's loop tracking. A dream-synthesized insight or a
correlation hypothesis is never itself a direct observation about the user or the world — it is
Ze's own inference *about* patterns it noticed in user/world data, i.e. squarely `self`-face
content, even when the hypothesis's evidence cites world-entity signals. This mirrors why
`Hypothesis.claim_kind` is always `INFERENCE`/`SUSPICION` (Ze's own belief), never `FACT` (a
direct claim about user/world) — the same reasoning extends to `target_face`.

## Summary of new dependencies

None. `ze-plugin` gains an import of `ze_agents.claims` (already an indirect dependency via the
producers) and `ze_agents.errors` (already used elsewhere in the repo's core packages). No new
third-party packages, no new services.
