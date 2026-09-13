# Feature Specification: Social Cognition Foundation

**Feature Branch**: `128-social-cognition-foundation`

**Created**: 2026-08-26

**Status**: Draft

**Input**: User description: "Social Cognition Foundation — phase 128, implementing steps 1
and 2 of specs/arch/social-cognition.md's phased rollout sketch (the reconciliation steps, not
step 3's new co-occurrence inference capability, which stays out of scope for a later phase).
Add `project` as a new entity_type in core/ze-memory; add `WORKS_ON` (person→project) and
`COLLABORATES_WITH` (person↔person) predicates to the memory graph's controlled vocabulary;
retrofit `Relationship.confidence` to the shared `Confidence`/`DecayProfile.TIME_LINEAR` type
and add a computed `last_contact` field; retire `plugins/ze-personal`'s dead
`PersonRelationship`/`contact_relationships` schema (zero production callers, no seed data —
confirmed by repo-wide grep); wire the existing `StaleFollowUpNudge`/
`list_stale_for_follow_up()` nudge into `core/ze-priority`'s `PriorityView` as a fourth ranked
source instead of its own independent, unbudgeted config threshold. Project-person
co-occurrence inference via `ze-correlation` is explicitly out of scope for this phase."

**Governed by**: [`specs/arch/social-cognition.md`](../../arch/social-cognition.md) (the
design brief this phase implements — rollout steps 1 and 2 only; step 3, co-occurrence
inference, is explicitly deferred to a later phase) and, transitively,
[`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) §The contribution model (social
cognition is licensed for `ClaimKind.IDENTITY` only) and
[`specs/arch/claim-topology.md`](../../arch/claim-topology.md) (the shared `Confidence`/decay
vocabulary this phase retrofits `Relationship.confidence` onto). Depends on
[`specs/phases/124-contribution-seam-core/spec.md`](../124-contribution-seam-core/spec.md)
(the `Contribution` write path `SourceFunction.SOCIAL_COGNITION` already uses for `Person` —
unchanged by this phase) and
[`specs/phases/123-attention-arbitration/spec.md`](../123-attention-arbitration/spec.md)
(`PriorityView` and the shared attention budget this phase routes relationship-staleness
nudges through). Does not build project-person co-occurrence inference — that is
`specs/arch/social-cognition.md`'s rollout step 3, gated on this phase shipping first per that
document's own sequencing.

---

## Overview

`specs/arch/social-cognition.md` found that Ze's social-cognition gap is narrower than it
first looked, and partly self-inflicted: `plugins/ze-personal` already has a `PersonRelationship`
type and a `contact_relationships` table, but they were never wired to any producer (zero
production callers beyond tests) — real schema that, had it been used, would have duplicated
`core/ze-memory`'s `memory_relationships` graph, the exact parallel-structure anti-pattern
`specs/arch/aperture-decision.md` warned against for open loops. Meanwhile `StaleFollowUpNudge`
*is* live in the morning briefing today, but predates `core/ze-priority`'s `PriorityView`
(Phase 123) and bypasses its shared attention budget with its own fixed-threshold config.

This phase is therefore reconciliation more than new-build: it gives Ze a `project` entity and
real, typed, decaying person↔person and person↔project edges in the one graph that already
exists, retires the dead parallel schema outright (there is no data to migrate), and folds the
one live relationship-facing nudge into the shared, budget-gated surfacing mechanism every
other attention-competing source already uses. It does not build any new inference — projects
and relationship edges are populated the same way contacts already are today (extraction from
conversation/email/calendar), and no automatic "these two people work together" conclusion is
drawn in this phase.

---

## Clarifications

### Session 2026-08-26

- Q: How is a `project` entity actually created — does this phase need a dedicated extraction
  path, or does it reuse the existing contact-extraction machinery? → A: Reuses the existing
  entity-extraction/upsert pattern `PersonStore._write_entity()` already established for
  `person` entities — a `project` is upserted into `core/ze-memory`'s entity table the same
  way, triggered from the same conversation/email/calendar extraction call sites that already
  produce `PersonCandidate`/`ContactProposal`-shaped output for people. This phase does not
  invent a new extraction pipeline; it extends the existing one to a second entity type.
- Q: Does retiring `contact_relationships` require a data migration or backward-compatibility
  shim? → A: No. Repo-wide search found zero production callers of
  `PersonStore.add_relationship()`/`get_relationships()` (only
  `plugins/ze-personal/tests/contacts/test_person_store.py` references them), and the table's
  own creation migration (`zc005_contacts_and_channels.py`) carries no seed data. This is a
  straight retirement — drop the table, delete the dead type and methods — not a migration.
- Q: What happens to the morning briefing's existing `stale_days`/`max_nudges` config keys once
  `list_stale_for_follow_up` is routed through `PriorityView`? → A: They stop governing the
  nudge directly. `specs/arch/social-cognition.md`'s risk section flags this explicitly as a
  real behavior change (the point of Phase 123 was exactly this consolidation), not a
  transparent refactor — the briefing reads `PriorityView`'s ranked, budget-gated output for
  its relationship-staleness line instead of calling the store method with its own threshold.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - People and projects live in one connected graph (Priority: P1)

As Ze, when I extract that the user is working on something with someone else — from an email
thread, a calendar invite, or something mentioned in conversation — I record both the project
and the person's involvement in it as durable, typed, provenanced state in the same memory
graph that already holds every other fact about the user's world, not in a separate table
nobody else can query.

**Why this priority**: This is the foundational capability everything else in
`specs/arch/social-cognition.md`'s rollout depends on — surfacing, correlation, and any future
relationship-aware behavior all need people and projects to exist as connected graph state
first.

**Independent Test**: Extract a project mention and a person's involvement in it from a
conversation. Query the memory graph (the existing `/brain/graph` view or `GraphStore.expand()`)
starting from either the person or the project entity and confirm the other is reachable via a
typed edge, with confidence and provenance attached.

**Acceptance Scenarios**:

1. **Given** a conversation, email, or calendar event that mentions the user is working on
   something with another person, **When** Ze extracts it, **Then** a `project`-typed entity
   and a `WORKS_ON` edge from the relevant `person` entity to it both appear in the memory
   graph, each carrying provenance and a confidence value.
2. **Given** two people are mentioned together in a way that implies a personal or professional
   connection between them (not mediated by a project), **When** Ze extracts it, **Then** a
   `COLLABORATES_WITH` edge is created between their two `person` entities.
3. **Given** an existing person↔project or person↔person edge, **When** the same relationship
   is mentioned again later, **Then** the edge's `confidence` is reinforced (not duplicated as
   a second edge) and its `last_contact` timestamp advances to the newer mention.

---

### User Story 2 - Relationship state is honest about staleness (Priority: P2)

As Ze, I want every person↔person and person↔project edge to carry a real confidence value that
falls over time using the same decay math every other claim in the system already uses, and a
`last_contact` timestamp computed from actual communication activity — not a value the user has
to remember to update by hand.

**Why this priority**: This is what makes the graph trustworthy as a *current* picture rather
than an append-only log nobody prunes — and it's the prerequisite for any future
staleness-aware surfacing (this phase's User Story 3, and later phases' correlation work).

**Independent Test**: Create an edge, advance time past one `TIME_LINEAR` decay period without
any new activity touching it, and confirm its `confidence` has decayed using the shared decay
function — not a bespoke relationship-specific formula. Separately, confirm `last_contact`
updates only from communication-graph activity, never from a manually-set value.

**Acceptance Scenarios**:

1. **Given** a person↔project or person↔person edge with a given `confidence`, **When** the
   shared `TIME_LINEAR` decay period elapses with no new corroborating activity, **Then** the
   edge's effective confidence, when read, reflects that decay using
   `ze_agents.claims.decay()` — the same function and rate every other `TIME_LINEAR`-decaying
   claim in the system uses.
2. **Given** a new message, meeting, or thread that touches both endpoints of an existing edge,
   **When** it is processed, **Then** that edge's `last_contact` timestamp is updated to reflect
   it, without any explicit user action.
3. **Given** no such activity has ever occurred for an edge beyond its creation, **When**
   `last_contact` is read, **Then** it reflects the edge's creation-triggering event, not a
   null or a manually-entered guess.

---

### User Story 3 - Stale-relationship nudges compete fairly for the user's attention (Priority: P2)

As the user, I want to be reminded about relationships going stale as one more input to Ze's
single ranked view of what deserves my attention today, not as an independent, unranked
message that shows up regardless of what else is competing for the same daily nudge budget.

**Why this priority**: Today's `StaleFollowUpNudge` behavior already works and shouldn't
regress, but it currently bypasses the shared attention budget entirely — this closes that gap,
consistent with why Phase 123 built `PriorityView` in the first place.

**Independent Test**: With loops, goals, and stale relationships all eligible to surface on the
same day and the shared attention budget only able to cover one, confirm the item `PriorityView`
ranks highest is the one that gets pushed — and that a stale relationship can be that
highest-ranked item, not just loops/goals/hypotheses.

**Acceptance Scenarios**:

1. **Given** one or more relationships due for a nudge per the existing stale-contact logic,
   **When** the morning briefing runs, **Then** it reads that nudge from `PriorityView`'s ranked
   output rather than calling `PersonStore.list_stale_for_follow_up()` directly with its own
   `stale_days` threshold.
2. **Given** a stale relationship and an eligible open loop on the same day, with the shared
   attention budget only able to surface one, **When** both are ranked, **Then** the one
   `PriorityView` scores higher is the one surfaced, and the other is not — matching Phase
   123's existing cross-mechanism ranking behavior for loops/goals/hypotheses.
3. **Given** `PriorityView`'s relationship-staleness source fails to answer, **When** the rest
   of `PriorityView` is queried, **Then** ranking continues over the sources that succeeded,
   per Phase 123's existing graceful-degradation behavior (FR-009).

---

### Edge Cases

- What happens when a `project` entity is extracted from a conversation but the user later
  clarifies it isn't a real ongoing project (e.g., a one-off errand mentioned in passing)? This
  phase does not add project-specific dismissal UX — the existing entity-review/dismissal
  pattern already used for pending contacts is the fallback, not a new mechanism.
- What happens to a person↔project edge when the person entity itself is later merged with a
  duplicate (existing entity-consolidation handles this) — does the edge survive the merge? The
  edge must be re-pointed to the surviving entity, not silently dropped, consistent with how
  the existing consolidator already preserves other entity relationships across merges.
- What happens if the same two people are extracted as both working on a shared project
  (`WORKS_ON` to the same project entity, implying collaboration) and separately extracted as
  directly `COLLABORATES_WITH` each other — is this a duplicate signal? No: `WORKS_ON` and
  `COLLABORATES_WITH` are independent edges: shared project membership does not automatically
  create or imply a direct `COLLABORATES_WITH` edge in this phase (that inference is explicitly
  out of scope — see step 3 of the arch doc's rollout, a later phase).
- What happens to in-flight or historical data referencing `contact_relationships` at the
  moment of the retiring migration? None exists (confirmed: no seed data, zero production
  writers) — the migration is a straight `DROP TABLE`, not a backfill.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add `project` as a valid value of `core/ze-memory`'s `entity_type`
  field, alongside the existing `person | org | topic | ticker | place | product` set.
- **FR-002**: System MUST add two new predicates, `WORKS_ON` and `COLLABORATES_WITH`, to
  `core/ze-memory`'s controlled relationship-predicate vocabulary, documented with the same
  one-line semantic comment convention as the existing predicates (e.g. `PARTICIPATES_IN`'s
  "event → entity" comment) — `WORKS_ON` is person → project; `COLLABORATES_WITH` is
  person ↔ person. Existing predicates, including `PARTICIPATES_IN`, MUST NOT be repurposed for
  this.
- **FR-003**: System MUST extract `project` entities and `WORKS_ON`/`COLLABORATES_WITH` edges
  using the same conversation/email/calendar extraction call sites and upsert pattern already
  used for `person` entities (mirroring `PersonStore._write_entity()`) — no new, separate
  extraction pipeline is introduced.
- **FR-004**: The memory graph's `Relationship.confidence` field MUST be retrofitted from a
  plain `float` to the shared `ze_agents.claims.Confidence` type, using
  `DecayProfile.TIME_LINEAR` — the same decay profile and rate already used by
  `HypothesisDecayJob`, the dream promoter, and `core/ze-priority`'s urgency scoring. No new,
  relationship-specific decay profile is introduced.
- **FR-005**: `Relationship` (or its storage layer) MUST carry a `last_contact` timestamp field
  that is set/updated only from processed communication-graph activity (a message, meeting, or
  thread touching both endpoints of the edge) — never manually settable by the user or any
  agent tool in this phase.
- **FR-006**: System MUST NOT introduce a separate user-settable "cadence" field, or any
  continuous multi-factor relationship-strength score, in this phase — `confidence` (via
  `TIME_LINEAR` decay) and `last_contact` are the only two pieces of relationship state this
  phase adds, per `specs/arch/social-cognition.md`'s "minimal, not a scoring engine" decision.
- **FR-007**: System MUST retire `plugins/ze-personal`'s `contact_relationships` table (via a
  new migration in ze-personal's `zc` chain), the `PersonRelationship` type, and
  `PersonStore.add_relationship()`/`get_relationships()` — with no data migration step, since
  no production caller and no seed data exist for any of them.
- **FR-008**: System MUST route `list_stale_for_follow_up`'s underlying signal through
  `core/ze-priority`'s `PriorityView` as a fourth ranked source (alongside loops, goals, and
  correlation hypotheses), participating in the same shared, atomically-claimed daily attention
  budget established in Phase 123 — not as an independently-thresholded, unranked channel.
- **FR-009**: The morning briefing (`ze_personal/jobs/briefing.py`) MUST read its
  relationship-staleness content from `PriorityView`'s ranked output rather than calling
  `PersonStore.list_stale_for_follow_up()` directly with its own `stale_days` config threshold.
- **FR-010**: `PriorityView` MUST continue to degrade gracefully if the relationship-staleness
  source fails to answer — ranking continues over the sources that succeeded, consistent with
  Phase 123's existing FR-009 behavior, now covering a fourth source.
- **FR-011**: System MUST NOT build project-person co-occurrence inference (deciding, from
  communication patterns, that two people who have never been directly linked probably work
  together) in this phase — that is `specs/arch/social-cognition.md`'s rollout step 3, explicit
  future work.
- **FR-012**: System MUST NOT introduce a closed taxonomy of person↔person relationship types
  beyond the single `COLLABORATES_WITH` predicate in this phase — `Person.classification`
  (already existing: `personal | professional | unknown`) remains the mechanism for
  distinguishing relationship domains, per `specs/arch/social-cognition.md`'s resolved decision.

### Key Entities

- **Project entity**: A `core/ze-memory` entity with `entity_type="project"`, extracted the
  same way person entities already are — a name/canonical identifier, aliases, and whatever
  attributes the existing entity-extraction path already captures generically. Not a new store;
  a new value of an existing field.
- **`WORKS_ON` edge**: A `memory_relationships` row with `predicate="WORKS_ON"`, source a
  `person` entity, target a `project` entity, carrying `confidence` (the retrofitted
  `Confidence` type) and `last_contact`.
- **`COLLABORATES_WITH` edge**: A `memory_relationships` row with
  `predicate="COLLABORATES_WITH"`, connecting two `person` entities, carrying the same
  `confidence`/`last_contact` shape as `WORKS_ON`.
- **PriorityView relationship-staleness source**: A fourth input to the existing `PriorityView`
  ranked-list query (alongside loops, goals, hypotheses), surfacing edges whose `last_contact`
  and decayed `confidence` indicate they're due for a nudge — not a new persisted entity, a new
  read-time source the existing view already knows how to combine.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every person↔project and person↔person relationship Ze knows about is reachable
  as a typed, provenanced edge from the single memory graph — querying from either endpoint
  (via the existing `/brain/graph` view or `GraphStore.expand()`) surfaces the other, with no
  relationship state living in a second, ungraphed table.
- **SC-002**: The `contact_relationships` table and its associated dead code no longer exist in
  the codebase after this phase ships, with zero regressions in any test suite that previously
  exercised it (those tests are removed, not left pointing at deleted code).
- **SC-003**: On any given day, when a stale relationship and another attention-competing item
  (a drifting loop, a stuck goal) are both eligible to surface and the shared daily budget can
  only cover one, the one actually surfaced to the user is always the one `PriorityView` ranks
  higher — never both, and never the stale-relationship nudge by default regardless of rank.
- **SC-004**: A relationship's confidence, read at any point after its last corroborating
  activity, reflects real elapsed-time decay computed via the same shared decay function every
  other `TIME_LINEAR` claim in the system uses — verified by a dedicated test showing the value
  actually falls over simulated elapsed time, not just that the field exists.

## Assumptions

- "Reconciliation, not new-build" governs this phase's scope: nothing here invents a new
  extraction pipeline, a new store, or a new decay formula — every mechanism reused
  (entity-extraction/upsert, `Confidence`/`TIME_LINEAR`, `PriorityView`'s ranking and shared
  budget) already exists and is exercised by at least one other producer today.
- `last_contact`'s "communication-graph activity" scope in this phase is whatever the existing
  perception layer already ingests (email, calendar, conversation) — no new channel integration
  is introduced to compute it.
- The briefing's `stale_days`/`max_nudges` config keys are not preserved with their old meaning;
  per `specs/arch/social-cognition.md`'s own risk note, this is a deliberate behavior change
  (the point of consolidating into `PriorityView`), not a compatibility requirement.
- Project entities, once extracted, do not get an explicit lifecycle state (no
  `active`/`closed`) in this phase, per `specs/arch/social-cognition.md`'s "don't formally close
  a project" decision — membership/relevance is a read-time concern for later surfacing work,
  not a write-time state machine this phase must build.
- This phase does not add any new REST endpoint or UI surface for browsing projects
  specifically — the existing `/brain/graph` entity view already generalizes to any
  `entity_type`, including the new `project` value, without dedicated new UI work.
