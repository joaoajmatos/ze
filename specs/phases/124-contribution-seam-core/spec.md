# Feature Specification: Contribution Seam Core — Typed Proposals + Reflection Migration

**Feature Branch**: `124-contribution-seam-core`

**Created**: 2026-08-25

**Status**: Planned

**Input**: User description: "Implement the first two phased-rollout steps of specs/arch/contribution-seam.md as one feature, mirroring the precedent set by Phase 111 (claim-topology) of shipping the shared type and its real retrofits together rather than splitting scaffolding from payoff: (1) define the Contribution type (claim_kind, provenance, confidence, target_face, source_function, evidence) in core/ze-plugin, built on the shared ze_agents.claims vocabulary from Phase 111; (2) retrofit Signal (core/ze-memory) to carry it — Signal already gained claim_kind/confidence in Phase 111's zm017 migration, this feature adds the missing provenance field and formalizes Signal as a Contribution subtype without replacing the SignalSource polling mechanism; (3) retrofit OpenLoop's extraction path (core/ze-worldstate) to produce typed Contributions while keeping its current direct-write mechanics; (4) migrate reflection — the dream pipeline (core/ze-memory/dream) and the correlation engine (core/ze-correlation) — onto the seam, so that dream artifact staging and correlation hypothesis generation both go through a validated Contribution write path that mechanically rejects any claim_kind=FACT proposal from those two sources. No consumer of signal_sources() is rewired — ze-correlation and ze-worldstate keep polling exactly as today; only the object shape and the reflection write path change. Arbitration in this feature is a validated write path (type + claim-kind license check), not real conflict resolution between competing contributions — that remains out of scope until a second function collides with an existing one on the same world-state face."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (constitutional —
§The contribution model: "reflection may never emit a fact" is this feature's load-bearing
rule), and [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md) (the design
brief this feature implements — phased-rollout steps 2 and 3; step 1, the executive layer, is
already done via `core/ze-worldstate`). Depends on
[`specs/arch/claim-topology.md`](../../arch/claim-topology.md) / Phase 111 (shipped — the
`ClaimKind`/`Provenance`/`Confidence` vocabulary this feature's `Contribution` type is built
directly on; `Signal` already carries `claim_kind`/`confidence` from that phase's `zm017`
migration). Does not build real cross-function arbitration (`contribution-seam.md`'s step 5) —
deferred until two functions demonstrably collide on the same world-state face, per that
document's own premature-abstraction guard.

---

## Overview

The doctrine names the direction explicitly: "every function contributes through the same
uniform proposal seam, rather than through ad-hoc writes to memory tables." Today exactly one
seam-shaped mechanism exists — `SignalSource` (Phase 60) — and even it is incomplete: `Signal`
is, in `contribution-seam.md`'s own words, "a private pull channel" between perception plugins
and two privileged consumers (`ze-correlation`, `ze-worldstate`), who poll it and then write
their *own* derived claims to the spine. Perception's raw signal never itself lands on the
shared world-state with honest provenance. Everything else — the dream pipeline's artifact
staging, the correlation engine's hypothesis generation, `OpenLoop`'s extraction path — writes
directly to its own store, each independently, with no shared notion of "a function is
proposing a change to the spine."

This is also where the doctrine's most safety-critical rule currently rests entirely on
discipline rather than enforcement: "reflection may never emit a fact." The dream pipeline
honours it today because its promotion gate happens to route synthesized artifacts through
NLI/critic checks before anything reaches `memory_facts`, and the correlation engine honours it
because `Hypothesis` happens to be a separate type from `memory_facts` rows. Both are true by
convention, not by a wall that a future change to either pipeline cannot cross without a type
error.

This feature closes that gap for the two producers where it matters most (`Signal` and
`OpenLoop`, per `contribution-seam.md`'s "two existing producers" framing) and, going one step
further than the document's minimal step-2 sketch (matching this repo's own Phase 111
precedent of shipping type-plus-real-retrofit as one feature rather than splitting scaffolding
from payoff), migrates reflection — the dream pipeline and the correlation engine — onto the
same typed write path. After this feature, "reflection may never emit a fact" is a property the
type system enforces for dream and correlation, not a property that happens to hold because
nobody has changed those pipelines yet in a way that breaks it.

No consumer of `signal_sources()` is rewired. `ze-correlation` and `ze-worldstate` keep polling
signals exactly as they do today — only the shape of what they poll, and how reflection writes,
changes.

## Clarifications

### Session 2026-08-25

- Q: Should the write path log a rejection (claim-kind license violation or missing/dangling
  evidence) in addition to raising a typed error to the caller? → A: Yes — a structured
  `WARNING`-level log via `get_logger` at the point of rejection, no new table.
- Q: What does "evidence references exist at submission time" validate against, given
  correlation's existing `EvidenceRef` already carries a heterogeneous `kind` (e.g. `"fact"`,
  `"signal"`) while the dream pipeline only cites `memory_facts`? → A: Validation is dispatched
  per evidence item's own kind tag to the matching store (fact → `memory_facts`, signal → the
  pinned signal store, etc.) — `evidence` is `EvidenceRef`-shaped, not a bare ID list, and the
  check generalizes `ze_correlation/engine.py`'s existing `cited_ids ⊆ known_ids` validation
  into the shared seam rather than reimplementing it per producer.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A shared `Contribution` type exists and `Signal`/`OpenLoop` use it (Priority: P1)

As a developer extending Ze (adding a plugin's `SignalSource`, or a new loop-extraction path), I
work against one typed `Contribution` shape — claim-kind, provenance, confidence, target world-state
face, source function, and evidence — instead of each producer inventing its own metadata fields.

**Why this priority**: Every other user story depends on this type existing first; it is also
independently valuable — it is the "one vocabulary" step the doctrine calls for.

**Independent Test**: Construct a `Contribution` from a `Signal` and from an `OpenLoop`
candidate. Assert both round-trip through the same type with `claim_kind`, `provenance`,
`confidence` populated from the shared `ze_agents.claims` vocabulary, and that `Signal`'s
existing `magnitude` (relevance) field is preserved as distinct from `confidence`.

**Acceptance Scenarios**:

1. **Given** a plugin's `SignalSource.poll()` returns a `Signal`, **When** it is wrapped as a
   `Contribution`, **Then** `claim_kind` is always `FACT` (perception's sole licensed kind),
   `provenance` is a real `Provenance` value (not the current bare `source: str`), and
   `confidence` and `magnitude` remain two distinct fields.
2. **Given** `OpenLoop`'s extraction path produces a candidate loop, **When** it is wrapped as a
   `Contribution`, **Then** the loop's existing `claim_kind`/`confidence` (already
   `ze_agents.claims`-typed since Phase 111) populate the `Contribution` without duplication or
   re-derivation.
3. **Given** the `Contribution` type, **When** inspected, **Then** it is defined once in
   `core/ze-plugin` and imported by every producer — no package redefines its own copy.

---

### User Story 2 - Reflection cannot submit a fact (Priority: P1)

As Ze, when the dream pipeline stages a synthesized artifact or the correlation engine generates
a hypothesis, the write path itself refuses the submission if it is tagged `claim_kind=FACT` —
the doctrine's rule is enforced at the point of writing, not just honoured by the pipelines'
current internal logic.

**Why this priority**: This is the feature's actual payoff — the doctrine calls this "the most
dangerous failure mode for a system that dreams," and it is the reason this feature exists
rather than stopping at User Story 1's type definition alone.

**Independent Test**: Submit a `Contribution` from the dream pipeline's staging path with
`claim_kind=FACT`. Assert the write path rejects it before it reaches any store. Submit the same
staging call with `claim_kind=INFERENCE` or `SUSPICION`. Assert it succeeds. Repeat for the
correlation engine's hypothesis-save path.

**Acceptance Scenarios**:

1. **Given** a dream-pipeline artifact contribution tagged `claim_kind=FACT`, **When** it is
   submitted through the seam's write path, **Then** the write is rejected with a typed error
   and nothing is persisted.
2. **Given** the same artifact tagged `claim_kind=INFERENCE` (the dream pipeline's actual,
   correct tagging today), **When** submitted, **Then** it is persisted exactly as the current
   direct-write path would have persisted it — no behavior change for correctly-tagged writes.
3. **Given** a correlation-engine hypothesis save, **When** submitted as a `Contribution`,
   **Then** its `claim_kind` is validated as `INFERENCE` or `SUSPICION` — never `FACT` — before
   `HypothesisStore.save()` is reached.

---

### User Story 3 - No behavior change for existing consumers (Priority: P2)

As the operator of Ze, after this feature ships, `ze-correlation` and `ze-worldstate` continue
polling `signal_sources()` and producing loops/hypotheses exactly as before — this feature does
not change what gets surfaced to the user, only how the underlying write is shaped and gated.

**Why this priority**: Lower priority than P1 because it's a non-regression guarantee, not new
capability — but explicitly required by the design brief ("no consumer is rewired yet").

**Independent Test**: Run the existing correlation and worldstate integration test suites
unmodified against the new `Contribution`-typed `Signal`/`OpenLoop` producers. Assert no test
behavior changes beyond type-shape adaptations at the call boundary.

**Acceptance Scenarios**:

1. **Given** the existing `ze-correlation` and `ze-worldstate` test suites, **When** run after
   this feature ships, **Then** all previously-passing assertions about surfaced
   loops/hypotheses/pushes still pass unchanged.

---

### Edge Cases

- What happens when a `Contribution`'s `claim_kind` doesn't match its `source_function`'s
  license (e.g. a `Signal` somehow tagged `INFERENCE` instead of the doctrine-mandated `FACT`
  for perception)? The write path MUST reject it the same way it rejects reflection-tagged
  facts — the licensing check is general, not reflection-specific.
- What happens to `evidence` (kind-tagged cited claim references) when an inference/suspicion
  contribution's cited facts don't exist or have already been retracted? The write path
  validates each evidence item against the store matching its own kind tag (fact →
  `memory_facts`, signal → the pinned signal store) at submission time; a dangling reference in
  any kind is rejected, not silently accepted.
- What happens on any rejection (claim-kind license violation, missing evidence, dangling
  evidence)? The write path emits a structured `WARNING`-level log via `get_logger` in addition
  to raising the typed error to the caller — rejections are never silent, but no new table or
  persisted audit trail is introduced (FR-012).
- What happens if the dream pipeline's promotion gate (NLI, adversarial critics) still wants to
  run on a submitted contribution before it's fully committed? The seam's write path validates
  claim-kind licensing and shape; it does not replace or bypass the existing promotion gate —
  gated promotion still runs on contributions the seam has accepted as correctly-typed.
- What happens for `OpenLoop` contributions that don't fit the `FACT`/`INFERENCE`/`SUSPICION`
  three used by perception/reflection — loops can carry `IDENTITY` or `PRIORITY` too? The
  licensing table is per-function, not a fixed three; the executive function's existing full
  claim-kind range continues to be honoured unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define a `Contribution` type in `core/ze-plugin` carrying
  `claim_kind` (`ze_agents.claims.ClaimKind`), `provenance` (`ze_agents.claims.Provenance`),
  `confidence` (`ze_agents.claims.Confidence`), `target_face` (which world-state face:
  self/user/world/active-concerns), `source_function` (which of the seven cognitive functions
  produced it), and `evidence` (a list of kind-tagged references — e.g. `("fact", id)`,
  `("signal", id)` — mirroring `ze_correlation.types.EvidenceRef`'s existing shape rather than a
  bare ID list; required for `INFERENCE`/`SUSPICION`).
- **FR-002**: `Signal` (`core/ze-memory`) MUST gain a `provenance` field typed as
  `ze_agents.claims.Provenance`, replacing reliance on the existing bare `source: str` for
  epistemic origin (the plugin-identifying `source` string itself is unaffected — it remains
  plugin-domain vocabulary per `specs/arch/plugin-domain-vocabulary.md`, not folded into
  `Provenance`).
- **FR-003**: `Signal` MUST be expressible as a `Contribution` with `claim_kind` fixed to `FACT`
  (perception's sole licensed claim-kind) — either by `Signal` becoming a `Contribution`
  subtype or by a lossless, tested conversion function; `magnitude` MUST remain a distinct field
  from `confidence`, not merged. `ze_memory.retriever.ingest_signal`, the real write path that
  persists a `Signal` to `memory_signals`, MUST route through the same validated write path as
  FR-005/FR-006 (general licensing check per FR-007, Edge Case 1) — the wrapper call, not the
  insert logic itself, is what changes.
- **FR-004**: `OpenLoop`'s extraction path (`core/ze-worldstate/ze_worldstate/extraction.py`)
  MUST produce `Contribution`-typed objects for candidate loops and route its `loop_store.create`
  call(s) through the same validated write path as FR-005/FR-006 (general licensing check per
  FR-007, Edge Case 1), while keeping its current direct-write *mechanics* unchanged — matching
  (dedup), entity linking, and the `loop_store.create` call signature are untouched; only a
  license-check gate is added in front of the existing call. This is a shape change plus a
  licensing gate, not a rewiring of how loops get created or matched.
- **FR-005**: The dream pipeline's artifact-staging write path (`core/ze-memory/ze_memory/dream`)
  MUST route through a `Contribution`-typed write that validates `claim_kind` against
  reflection's license (`INFERENCE` or `SUSPICION` only) before any artifact is persisted, and
  MUST reject any contribution tagged `claim_kind=FACT` from this source.
- **FR-006**: The correlation engine's hypothesis-save path (`core/ze-correlation/ze_correlation/engine.py`)
  MUST route through the same `Contribution`-typed write and MUST reject any contribution tagged
  `claim_kind=FACT` from this source, using the identical validation logic as FR-005 (one
  licensing check, not two independent reimplementations).
- **FR-007**: The claim-kind licensing check MUST be general-purpose (keyed on
  `source_function` → allowed `claim_kind`s per the doctrine's contribution model table), not
  hardcoded to reject only reflection specifically — so the same mechanism also rejects, e.g., a
  malformed `Signal` contribution tagged anything other than `FACT`.
- **FR-008**: This feature MUST NOT rewire `ze-correlation` or `ze-worldstate`'s consumption of
  `signal_sources()` — both continue polling exactly as today; only the object shape of what
  they receive, and the reflection write path, change.
- **FR-009**: This feature MUST NOT implement cross-contribution conflict arbitration (two
  different functions' contributions disagreeing about the same claim) — the write path in this
  feature is a validated single-contribution path (type + claim-kind license check), not a
  precedence-ordered arbiter between competing contributions.
- **FR-010**: The existing dream pipeline promotion gate (NLI groundedness checks, adversarial
  critics, session diversity/temporal spread) MUST continue running unchanged on
  correctly-typed contributions the seam's write path has accepted — the seam validates shape
  and license, it does not replace domain-specific promotion logic.
- **FR-011**: `INFERENCE`/`SUSPICION`-kind contributions MUST include non-empty `evidence`
  (cited claim references); the write path MUST reject a contribution of those kinds with empty
  evidence, and for each non-empty evidence item MUST dispatch existence validation to the store
  matching that item's own kind tag (fact → `memory_facts`, signal → the pinned signal store,
  etc.) — a dangling reference in any one kind is rejected the same way as an empty list.
- **FR-012**: The write path MUST emit a structured `WARNING`-level log (via `get_logger`) at
  the point of any rejection (claim-kind license violation, missing evidence, or dangling
  evidence reference), in addition to raising the typed error to the caller — no new table or
  persisted audit trail is required beyond this log line.

### Key Entities

- **Contribution**: A function's typed proposal to change the world-state — `claim_kind`,
  `provenance`, `confidence`, `target_face`, `source_function`, `evidence` (a list of
  kind-tagged references, e.g. `("fact", id)`, mirroring `ze_correlation.types.EvidenceRef`).
  Defined once in `core/ze-plugin`, consumed by every retrofitted producer.
- **Signal (retrofitted)**: Perception's existing candidate-signal type
  (`core/ze-memory/ze_memory/types.py`), gaining a typed `provenance` field and expressible as a
  `FACT`-kind `Contribution`.
- **OpenLoop candidate (retrofitted)**: The executive function's existing loop-extraction
  output, now shaped as a `Contribution` at the point of proposal while its store-write
  mechanics stay unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reflection-originated write (dream artifact or correlation hypothesis) tagged
  `claim_kind=FACT` is rejected 100% of the time, verified by a dedicated test for each of the
  two reflection producers — not merely "no observed violation in current code paths."
  ​
- **SC-002**: Existing correlation and worldstate proactive behavior (what gets surfaced, when,
  under what push-budget conditions) is unchanged after this feature ships — zero regressions in
  their existing test suites beyond type-shape adaptations at call boundaries.
- **SC-003**: A developer adding a new perception `SignalSource` or a new executive extraction
  path needs to learn one `Contribution` shape, not a per-producer bespoke metadata convention —
  verified by both existing producers (`Signal`, `OpenLoop`) and the two migrated reflection
  producers sharing one type definition with zero producer-local duplicate fields for
  claim-kind/provenance/confidence.

## Assumptions

- "Validated write path" in this feature means: construct a `Contribution`, check its
  `claim_kind` against its `source_function`'s license, check `evidence` is present when
  required, then call through to the existing store write (`ze_memory.retriever.ingest_signal`,
  `loop_store.create`,
  `dream_store.save_artifact`, `HypothesisStore.save`) — it is a guard function/wrapper, not a
  new persisted queue or a new database table for every producer.
- The dream pipeline's existing staging mechanism (artifact save → gated promotion) is not
  replaced by a new queue; "migrate reflection onto the seam" means its write call goes through
  the new validated path, not that the staging/promotion architecture is redesigned.
- No new Alembic migrations are required beyond `Signal`'s `provenance` column — `Signal`
  already has `claim_kind`/`confidence` from Phase 111's `zm017`; `OpenLoop` already has its
  full claim-topology fields from `zw001`/Phase 111; the dream and correlation stores' existing
  columns already carry what a correctly-typed contribution needs, per Phase 111's retrofit.
- `target_face` and `source_function` are new metadata this feature introduces (not present on
  any producer today) — their enum values are derived directly from the doctrine's own four
  world-state faces and seven cognitive functions, not invented here.
- Real arbitration between competing contributions (contribution-seam.md's step 5) remains
  explicitly out of scope; this feature's "arbitration" is solely the claim-kind license check
  described in FR-007, applied to a single contribution at a time.
