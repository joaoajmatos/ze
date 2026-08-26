# Feature Specification: Contribution Seam Extension — Social Cognition + Action

**Feature Branch**: `125-contribution-seam-extension`

**Created**: 2026-08-25

**Status**: Done

**Input**: User description: "Implement the remaining low-urgency steps of specs/arch/contribution-seam.md's phased rollout — step 4, migrating social cognition and action onto the Contribution seam defined and proven by Phase 124 (Contribution Seam Core). Social cognition: ze-personal's contact/relationship pipeline (Person, PersonRelationship, ContactProposal in plugins/ze-personal/ze_personal/contacts/) currently carries its own bespoke confidence floats and bare source_type strings, with no claim_kind or typed provenance — the same gap claim-topology.md found and fixed in ze-worldstate/ze-correlation/ze-memory/ze-plugin's Signal, just never extended to contacts. This feature retrofits Person/PersonRelationship/ContactProposal onto the shared ze_agents.claims vocabulary and wraps contact-store writes (consolidator.py's _store_candidate, extractors) through the same Contribution-typed validated write path Phase 124 built, with claim_kind fixed to IDENTITY (social cognition's licensed kind per the doctrine's contribution model table, since a contact/relationship claim is a stable truth about who someone is to the user, not a fact about the world at large). Action: AgentResult's existing memory_proposals and contact_proposals fields become typed Contribution lists instead of untyped lists, so an agent's proposed side effects carry the same shape as everything else in the seam; the actual message/tool-call trace record_trace already writes a grounded record of what happened, not a claim, and this feature does not add a Contribution wrapper around record_trace itself since the doctrine's action license is 'records of what it did,' which record_trace already satisfies without needing epistemic metadata. Explicitly low urgency (per contribution-seam.md, 'as convenience allows') — no discovered live bug this feature fixes, unlike Phase 124's reflection-fact violation risk. Still excludes real cross-contribution arbitration (step 5)."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (constitutional —
§The contribution model: social cognition's `identity`/`relationship` license, action's
`records of what it did` license), and
[`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md) (the design brief — phased
rollout step 4). Depends on
[`specs/phases/124-contribution-seam-core/spec.md`](../124-contribution-seam-core/spec.md) (the
`Contribution` type and validated write path this feature extends to a third and fourth
producer) and, transitively,
[`specs/arch/claim-topology.md`](../../arch/claim-topology.md) / Phase 111 (the shared
`ClaimKind`/`Provenance`/`Confidence` vocabulary). Does not build real cross-contribution
arbitration (`contribution-seam.md`'s step 5) — still deferred, unchanged from Phase 124's
scoping.

---

## Overview

`specs/arch/claim-topology.md`'s 2026-07 mapping pass found the doctrine's epistemic ontology
implemented four different ways across `ze-worldstate`, `ze-correlation`, `ze-memory`, and
`ze-plugin`'s `Signal`, and Phase 111 unified all four. That pass did not cover
`ze-personal`'s contact/relationship pipeline, which has the identical shape of gap: `Person`,
`PersonRelationship`, and `ContactProposal` (`plugins/ze-personal/ze_personal/contacts/types.py`)
each carry their own bespoke `confidence: float` and a bare `source_type: str`, with no
`claim_kind` field and no typed `Provenance` — the same pattern claim-topology fixed elsewhere,
just never extended to social cognition because it wasn't in that pass's scope.

Phase 124 (Contribution Seam Core) proved the `Contribution` type and its validated write path
against two producers (`Signal`, `OpenLoop`) and the two reflection sources where a real safety
gap existed (dream, correlation). This feature is the natural extension: retrofit `Person`
family types onto the same shared vocabulary, route contact-store writes through the same
validated write path with `claim_kind` fixed to `IDENTITY` (social cognition's licensed kind —
a contact or relationship is a stable truth about who someone is to the user, matching the
doctrine's identity-claim definition, not a discrete fact about the world), and give action's
existing proposal fields (`AgentResult.memory_proposals`, `AgentResult.contact_proposals`) the
same typed shape as everything else moving through the seam.

Unlike Phase 124, this feature does not close a live safety gap — the doctrine's own
contribution-model table already lists social cognition and action as low-distance-to-seam,
low-risk producers ("Migrate after executive," "low priority — side effects, already
grounded"). It exists to finish the vocabulary's coverage, not to fix a discovered violation.

## Clarifications

### Session 2026-08-26

- Q: `Person`'s aggregate `confidence` is derived as `max(source.weight)` across multiple `PersonSource` rows, each with its own `source_type`. Should `PersonSource` also be retrofitted onto the shared vocabulary, or does `Person`'s `Provenance` get derived once from the winning source? → A: Retrofit `PersonSource` too — it gains `claim_kind`/`provenance` alongside its existing `source_type`/`weight`, so every source record carries typed provenance, not just the aggregate `Person`.
- Q: No existing job decays contact confidence today and no other producer assigns a `DecayProfile` to an `IDENTITY`-kind claim. Which `DecayProfile` should identity-claim `Confidence` use on `Person`/`PersonRelationship`/`ContactProposal`/`PersonSource`? → A: `EVIDENCE_WEIGHTED` — matches the doctrine's "requires repeated counter-evidence" identity-claim posture, even though no job currently invokes `decay()` for these types.
- Q: `AgentResult.memory_proposals`/`.contact_proposals` become typed `Contribution` lists (FR-005), and `Contribution` requires a `source_function`. `_LICENSE[SourceFunction.ACTION]` is empty, so tagging these `ACTION` would make them unlicensed by construction. What `source_function` should they carry? → A: Tag by originating claim kind — `memory_proposals` entries carry `SourceFunction.PERCEPTION` (licensed for `FACT`), `contact_proposals` entries carry `SourceFunction.SOCIAL_COGNITION` (licensed for `IDENTITY` after this feature), matching each proposal's actual epistemic origin rather than the agent-turn container.
- Q (raised during `/speckit-plan`): `ze_plugin.contribution.Contribution` is a metadata-only envelope (`claim_kind`/`provenance`/`confidence`/`target_face`/`source_function`/`evidence`) with no content payload, and the spec's own Assumptions bar modifying its shape — but `memory_hooks.py`'s `_write_contact_proposals` reads `proposal.name`/`.classification`/`.contact_info` today, fields `Contribution` doesn't have. Should FR-005's fields literally hold `Contribution`, or the domain type carrying the same vocabulary fields? → A: The domain type carries the vocabulary — `AgentResult.contact_proposals` stays `list[ContactProposal]` (now carrying `claim_kind`/`provenance`/`confidence` per FR-001/002 directly), and `AgentResult.memory_proposals` becomes `list[Fact]` (`ze_memory.types.Fact`, which already carries `confidence`/`provenance`). A `Contribution` envelope is built transiently only at the write boundary (mirroring `signal_to_contribution()`/`loop_to_contribution()`), never stored on `AgentResult` — this is what "typed Contribution lists" means in the Overview/Input, not a literal `list[Contribution]` field.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contact and relationship claims carry the shared vocabulary (Priority: P1)

As a developer working on the contacts pipeline, `Person`, `PersonRelationship`, and
`ContactProposal` carry `claim_kind`/`provenance`/`confidence` from `ze_agents.claims`, the same
way `OpenLoop` and `Signal` already do — not a fourth bespoke confidence-float convention.

**Why this priority**: This is the concrete gap the feature exists to close; every other user
story builds on it.

**Independent Test**: Construct a `Person` and a `ContactProposal` from a conversation
extraction. Assert both carry `claim_kind=IDENTITY`, a `Provenance` value derived from their
existing `source_type`, and a `Confidence` value derived from their existing bespoke
`confidence` float — with no loss of the existing `SOURCE_WEIGHTS`-derived weighting behavior.

**Acceptance Scenarios**:

1. **Given** a `ContactProposal` produced by conversation extraction, **When** inspected,
   **Then** it carries `claim_kind=IDENTITY`, a typed `Provenance`, and a `Confidence` whose
   numeric value matches what the current bespoke `confidence: float` would have been.
2. **Given** a `PersonRelationship` between two people, **When** inspected, **Then** it also
   carries the shared vocabulary fields, consistent with `Person`.

---

### User Story 2 - Contact-store writes go through the validated write path (Priority: P1)

As Ze, when the contacts consolidator or an extractor proposes a new or updated `Person`, the
write goes through Phase 124's validated `Contribution` write path, which rejects any
social-cognition-originated write tagged with a `claim_kind` other than `IDENTITY` — the same
mechanical enforcement Phase 124 gave reflection, extended to this third producer.

**Why this priority**: Without this, User Story 1's typed fields exist but nothing actually
enforces them at the write boundary — same gap Phase 124 closed for reflection, applied here.

**Independent Test**: Submit a contact contribution tagged `claim_kind=FACT` (an incorrect
tagging) through `_store_candidate`'s write path. Assert it is rejected using the same general
licensing check Phase 124 built (FR-007 of that spec), not a new reimplementation.

**Acceptance Scenarios**:

1. **Given** a `ContactProposal` correctly tagged `claim_kind=IDENTITY`, **When** submitted
   through `consolidator.py`'s `_store_candidate`, **Then** it is persisted exactly as the
   current direct `store.upsert(person)` call would have persisted it — no behavior change for
   correctly-tagged writes.
2. **Given** a contact contribution incorrectly tagged with any `claim_kind` other than
   `IDENTITY`, **When** submitted, **Then** the write is rejected before `store.upsert()` is
   reached, using Phase 124's existing general-purpose licensing check.

---

### User Story 3 - Agent-proposed side effects carry the same shape (Priority: P2)

As a developer reading `AgentResult`, `memory_proposals` and `contact_proposals` are typed
`Contribution` lists — an agent's proposed side effects look like every other proposal moving
through the seam, not a pair of loosely-typed `list` fields.

**Why this priority**: Lower priority than P1/P2 above because it's a type-shape improvement on
an existing, already-working path (agents already propose facts/contacts successfully today) —
not a new enforcement boundary. `record_trace` itself is explicitly out of scope (see FR-008).

**Independent Test**: Inspect `AgentResult.contact_proposals` after an agent turn that proposes
a contact. Assert entries are `ContactProposal`s carrying `claim_kind=IDENTITY`/`provenance`/
`confidence`, satisfying the new `ClaimBearingProposal` Protocol — not the current untyped
`list`.

**Acceptance Scenarios**:

1. **Given** an agent turn producing a contact proposal, **When** `AgentResult` is inspected,
   **Then** `contact_proposals` is `list[ClaimBearingProposal]` populated with `ContactProposal`
   entries carrying `claim_kind=IDENTITY` and the shared vocabulary fields directly.
   `memory_proposals` is typed `list[ClaimBearingProposal]` too but stays unpopulated — no
   producer exists for it today, and this feature does not add one.

---

### Edge Cases

- What happens to a `Person` record created before this feature ships (no `claim_kind`/typed
  `provenance` on the existing row)? Backfill defaults to `claim_kind=IDENTITY` and derives
  `Provenance` from the existing `source_type` string via the same mapping used for new writes —
  consistent with how Phase 111 backfilled `memory_facts`/`correlation_hypothesis`.
- What happens when a `PersonRelationship`'s `confidence` was manually set by the user (i.e. the
  identity claim should decay slowest per the doctrine, "protected against churn")? The
  retrofit MUST preserve the doctrine's identity-claim decay posture (slow, requires repeated
  counter-evidence) — it does not introduce faster decay just because the type changed.
- What happens if `AgentResult.contact_proposals` includes a proposal for a person who already
  exists with conflicting classification? Unchanged from today — this feature retypes the
  proposal list, it does not change the existing consolidator's dedup/merge logic.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `Person`, `PersonRelationship`, `ContactProposal`, and `PersonSource`
  (`plugins/ze-personal/ze_personal/contacts/types.py`) MUST gain `claim_kind` (fixed to
  `IDENTITY`, the doctrine-licensed kind for social cognition) and typed `provenance`
  (`ze_agents.claims.Provenance`, derived from the existing `source_type: str` values via a
  documented mapping) fields. `PersonSource` — the per-source record that actually carries
  `source_type`/`weight` and from which `Person.confidence` is aggregated as
  `max(source.weight)` — gains these fields alongside its existing `source_type`/`weight`,
  not just the aggregate `Person`.
- **FR-002**: The existing bespoke `confidence: float` fields on `Person`/`ContactProposal`/
  `PersonRelationship`/`PersonSource` MUST be expressed via `ze_agents.claims.Confidence` —
  numeric values preserved, `SOURCE_WEIGHTS`-derived weighting behavior unchanged. The
  `Confidence.decay_profile` MUST be `DecayProfile.EVIDENCE_WEIGHTED`, matching the doctrine's
  "requires repeated counter-evidence" identity-claim decay posture (FR-007) — no decay
  invocation is added by this feature; the field is populated for future wiring.
- **FR-003**: Contact-store writes originating from the consolidator
  (`consolidator.py::_store_candidate`) and extractors (`extractors.py`) MUST route through
  Phase 124's validated `Contribution` write path before reaching `PersonStore.upsert()`.
- **FR-004**: The write path MUST reject any social-cognition-originated contribution whose
  `claim_kind` is not `IDENTITY`, using the identical general-purpose licensing check Phase 124
  built (not a new, parallel implementation).
- **FR-005**: `AgentResult.memory_proposals` and `AgentResult.contact_proposals`
  (`core/ze-agents/ze_agents/types.py`) MUST carry the same claim vocabulary as everything else
  moving through the seam, expressed as `list[ClaimBearingProposal]` — a new `runtime_checkable`
  `Protocol` defined in `ze_agents.types` (`claim_kind: ClaimKind`, `provenance: Provenance`,
  `confidence: float`), mirroring the existing `LLMClient`/`DBPool` Protocol pattern in the same
  package. `ze-agents` MUST NOT import `ContactProposal`, `Fact`, or `Contribution` directly —
  each sits above `ze-agents` in the package graph, and importing any of them would invert it
  (Principle III). `contact_proposals` is populated with `ContactProposal` instances, which
  satisfy the Protocol once FR-001/FR-002 add matching `claim_kind`/`provenance`/`confidence`
  fields; `memory_proposals` stays unpopulated (zero current producers), typed against the
  Protocol for whichever future producer populates it — this feature does NOT retrofit
  `ze_memory.types.Fact` itself (out of scope; `Fact.provenance` stays untyped `str` and it gains
  no `claim_kind` field). This feature MUST NOT change `ze_plugin.contribution.Contribution`'s
  shape to add a content payload — a transient `Contribution` envelope is built only at each
  proposal's write boundary (mirroring `signal_to_contribution()`/`loop_to_contribution()`),
  never stored on `AgentResult`, tagged `SourceFunction.SOCIAL_COGNITION` for `contact_proposals`
  writes — not `SourceFunction.ACTION`, which `_LICENSE` licenses for nothing.
- **FR-006**: Existing `Person` rows created before this feature ships MUST be backfilled with
  `claim_kind=IDENTITY` and a `Provenance` derived from their existing `source_type` value via
  the same mapping FR-001 defines for new writes.
- **FR-007**: The retrofit MUST NOT change the doctrine's identity-claim decay posture (slow,
  requires repeated counter-evidence) — confidence values are re-typed, not re-computed with a
  different decay rate.
- **FR-008**: This feature explicitly MUST NOT wrap `record_trace` (the action function's
  existing grounded record of what an agent did) in a `Contribution` — the doctrine's action
  license ("records of what it did") is already satisfied by `record_trace`'s existing shape,
  and it carries no epistemic claim requiring `claim_kind`/`provenance`/`confidence` metadata.
- **FR-009**: This feature MUST NOT implement cross-contribution conflict arbitration —
  unchanged scope exclusion from Phase 124.
- **FR-010**: This feature MUST NOT change the consolidator's existing dedup/merge logic for
  conflicting contact proposals — only the proposal and write-path types change.

### Key Entities

- **Person / PersonRelationship / ContactProposal / PersonSource (retrofitted)**: Social
  cognition's existing contact/relationship types
  (`plugins/ze-personal/ze_personal/contacts/types.py`), gaining `claim_kind=IDENTITY` and
  typed `provenance`/`confidence` from the shared vocabulary. `PersonSource` (the per-source
  record `Person.confidence` is aggregated from) is retrofitted alongside the other three, not
  left as a bespoke internal record.
- **AgentResult.memory_proposals / .contact_proposals (retyped)**: Action's existing
  agent-turn-output proposal lists, both retyped `list[ClaimBearingProposal]` — a new
  core-owned Protocol (`ze_agents.types`), not the concrete producer types, to respect the
  package graph. `contact_proposals` is populated with `ContactProposal` instances (carrying
  the vocabulary fields via FR-001/FR-002); `memory_proposals` stays unpopulated (no producer
  exists today). A transient `Contribution` envelope is built only at each proposal's write
  boundary, never stored on `AgentResult`.
- **ClaimBearingProposal (new)**: A `runtime_checkable` `Protocol` in
  `core/ze-agents/ze_agents/types.py` (`claim_kind`/`provenance`/`confidence`), mirroring the
  existing `LLMClient`/`DBPool` Protocol pattern, letting `AgentResult` reference the seam's
  vocabulary shape without importing any producer's concrete type.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A contact/relationship write tagged with any `claim_kind` other than `IDENTITY`
  is rejected 100% of the time, verified by a dedicated test — mirroring Phase 124's SC-001 for
  reflection.
- **SC-002**: Existing contact consolidation/extraction behavior (what gets proposed, how
  conflicts are resolved, decay posture for identity claims) is unchanged after this feature
  ships — zero regressions in the existing `ze-personal` contacts test suite beyond type-shape
  adaptations at call boundaries.
- **SC-003**: All four originally-unified producers from claim-topology (`OpenLoop`, `Signal`,
  `Hypothesis`, `memory_facts`) plus the two Phase 124 reflection producers plus this feature's
  social-cognition producer (`Person` family) share one `Contribution`/`ze_agents.claims` type
  definition — zero remaining producer-local bespoke confidence/provenance conventions among
  the seven cognitive functions' write paths, except action's `record_trace`, which FR-008
  establishes is correctly exempt.

## Assumptions

- The `source_type` → `Provenance` mapping for contacts (`"manual"`, `"conversation"`,
  `"email"`, `"calendar"`, `"research"` today) maps onto the existing closed `Provenance` enum
  (`graph_recall`/`live_search`/`prompt_supplied`/`synthesized`) the same way `OpenLoop`'s
  inflow-specific provenance values were resolved during Phase 111/`plugin-domain-vocabulary.md`
  — the exact mapping is a planning-time detail, not fixed by this spec.
- This feature reuses Phase 124's validated write path and licensing check as-is; it does not
  modify or extend that mechanism's shape, only registers a third caller against it.
- No new Alembic migrations beyond adding `claim_kind`/`provenance` columns (and backfill) to
  whatever table(s) back `Person`/`PersonRelationship` today — consistent with Phase 111's
  `zm016`/`zm017`/`zw001`-style additive-column pattern.
- "Low urgency" per the design brief means this feature is safe to defer indefinitely without
  accruing further risk (unlike Phase 124, which closed a live doctrine violation) — it is
  queued and ready, not blocking anything.
