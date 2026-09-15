# Feature Specification: Memory Facts Hard-Cut onto Shared Claim Vocabulary

**Feature Branch**: `134-memory-facts-hard-cut`

**Created**: 2026-09-15

**Status**: Implemented

**Input**: User description: "Spec 6 of specs/arch/contribution-seam.md phased rollout. Hard-cut Fact and memory_facts onto ze_agents.claims ClaimKind / Provenance / Confidence for real. Drop Fact.provenance string dialect raw/synthesized. Persist doctrine Provenance on insert. Update retrieval SQL that COALESCE(provenance, 'raw'). Remove propose_facts as a public ungated MemoryStore API in the same phase as the schema cut (private to the Contribution write= callback or deleted). Pre-v1: break the schema; no dual-write; no shim. Depends on Spec 5 (perception facts on the seam, phase 133): all remaining callers already submit via Contribution. Do not duplicate 133's call-site migration. If 133 missed a caller, 134 must not leave a public propose_facts door — call that out as a blocker rather than wrapping."

**Governed by**: [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md) (rollout
step 6), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md) (leftover on the fact
row after Phase 111), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md)
(constitution Principle VIII — no wrap-then-replace across phases; schema churn allowed),
[`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (epistemic ontology; honest
provenance), [`specs/arch/plugin-domain-vocabulary.md`](../../arch/plugin-domain-vocabulary.md)
(`Provenance` stays the four doctrine categories). **Depends on** [`specs/phases/133-perception-facts-seam/spec.md`](../133-perception-facts-seam/spec.md)
(contribution-seam rollout **step 5**): that phase has already routed every remaining
`propose_facts` caller through `Contribution`. This phase does not migrate call sites.

---

## Overview

Phase 111 put `claim_kind` on `memory_facts` and swapped dream decay onto the shared
`TIME_LINEAR` math, but a remembered fact still speaks a private dialect: `Fact.provenance` is
a string defaulting to `"raw"`, the row still stores `"raw"` / `"synthesized"`, retrieval
treats a missing value as `"raw"`, and `MemoryStore.propose_facts()` remains a public ungated
write. After the contribution seam's perception-facts phase (133), those writes are supposed to
arrive as `Contribution`s; the leftover dialect and the leftover door are this phase.

This feature finishes the leftover. A remembered fact uses the same `ClaimKind` /
`Provenance` / `Confidence` vocabulary as `Signal` and `Contribution`. Doctrine provenance is
required on insert. The public `propose_facts` method is gone when this phase is Done — the
only persist path is the seam's store write callback (or an equivalent private helper that
callback owns). There is no dual-write, no deprecated alias, and no later cleanup phase for the
door.

If 133 missed a caller, this phase **fails closed**: it does not restore a public
`propose_facts` API so that caller can keep compiling. That miss is a blocker on 133, recorded
in this spec's Edge Cases, not a reason to wrap.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A remembered fact carries doctrine provenance, not a private dialect (Priority: P1)

When Ze remembers something about the user — from a conversation, a document, or a later
synthesis — the stored fact says *how that claim entered reasoning* using the same four
epistemic origins every other claim already uses (graph recall, live search, prompt-supplied,
synthesized). It does not say `"raw"`. Missing provenance is not silently filled in as
`"raw"`.

**Why this priority**: This is the leftover from claim topology. Until the row and the
dataclass speak the shared vocabulary, contribution-seam step 6 is incomplete and retrieval
still special-cases a dialect no other producer has.

**Independent Test**: Insert a fact through the seam write path with doctrine provenance
`prompt_supplied`; read it back from retrieval and from any quality/digest surface that
exposes provenance; confirm the value is `prompt_supplied` (not `raw`). Repeat with
`synthesized`. Confirm a row with null provenance cannot be inserted.

**Acceptance Scenarios**:

1. **Given** a new fact submitted with epistemic origin "prompt-supplied", **When** it is
   persisted and later retrieved, **Then** its provenance is the shared `prompt_supplied`
   value and never the string `raw`.
2. **Given** a synthesized, uncorroborated fact, **When** it is persisted and later retrieved,
   **Then** its provenance is the shared `synthesized` value, and existing decay eligibility
   that used to key off `provenance = 'synthesized'` still selects that row.
3. **Given** an attempt to persist a fact with empty or unknown provenance, **When** the write
   runs, **Then** the write is rejected; retrieval no longer coalesces missing provenance to
   `raw`.
4. **Given** existing local rows that still store `raw` or null provenance, **When** this
   phase's migration runs, **Then** every row has a non-null doctrine provenance (`raw` and
   null map to `prompt_supplied`; `synthesized` stays `synthesized`); zero rows remain in the
   old dialect.

---

### User Story 2 - There is no public ungated door to write facts (Priority: P1)

After 133, perception already proposes facts as contributions. This phase removes the old
public store method so memory cannot be used as an accidental writer. Callers that still
imported `propose_facts` after 133 do not get a compatibility wrapper.

**Why this priority**: Pre-v1 hard cuts and contribution-seam step 6 both require the door
gone in the same phase as the schema cut. A typed row with a public back door is still two
seams.

**Independent Test**: The public memory-store contract no longer lists `propose_facts`.
A search of production code finds no remaining public calls. The seam write callback (or its
private helper) still persists facts and still runs contradiction checking. Tests that used
to call `propose_facts` go through that callback or are updated to the private helper.

**Acceptance Scenarios**:

1. **Given** the memory-store public contract after this phase, **When** a new module tries to
   call `propose_facts`, **Then** that method is not part of the contract (it is absent, not
   deprecated).
2. **Given** a valid perception `Contribution` with `claim_kind=FACT`, **When** it is submitted
   through the existing seam, **Then** the fact is persisted via the private write callback
   with doctrine provenance taken from the contribution (not rewritten to `raw`).
3. **Given** a remaining production caller of `propose_facts` that 133 missed, **When** this
   phase is implemented, **Then** work stops and the miss is treated as a 133 blocker — the
   public method is not put back.

---

### User Story 3 - Claim kind and confidence on a fact are the shared types, not table folklore (Priority: P2)

A `Fact` value in memory carries `claim_kind` from the shared enumeration (already on the row
since Phase 111, missing on the dataclass) and uses the shared confidence/decay vocabulary
(`TIME_LINEAR` on synthesized uncorroborated rows, unchanged cliffs). Reading code does not
infer kind from `"raw"` vs `"synthesized"` strings.

**Why this priority**: Completes "use ClaimKind / Provenance / Confidence for real" on the
fact type. Secondary to P1 because the row already has `claim_kind` and already decays via
shared math; the dataclass and the remaining string switches are the gap.

**Independent Test**: Constructing and reading a `Fact` requires a shared `ClaimKind`. Write
paths that previously derived `claim_kind` from `provenance == "synthesized"` use the fact's
`claim_kind` field (or the 111 rule expressed in shared types). Dream decay still selects
synthesized uncorroborated rows using doctrine provenance `synthesized`.

**Acceptance Scenarios**:

1. **Given** a persisted fact, **When** it is loaded into the `Fact` type, **Then**
   `claim_kind` is a shared `ClaimKind` value and `provenance` is a shared `Provenance` value.
2. **Given** the 111 rule (observed/corroborated → `FACT`; synthesized uncorroborated →
   `INFERENCE`), **When** a fact is written without an explicit kind, **Then** kind is set
   from that rule using doctrine provenance, not the strings `raw` / `synthesized`.
3. **Given** synthesized uncorroborated facts older than the decay window, **When** the dream
   decay pass runs, **Then** confidence still decreases via the shared `TIME_LINEAR` function
   with the same 0.50 / 0.25 cliffs.

---

### Edge Cases

- **133 missed a caller**: production still calls `propose_facts` (conversation
  `write_memory`, ingestion `MemorySink`, messenger inbound, onboarding memory-fact seeds,
  goal-learning promotion, or any other site). This phase does **not** wrap. Implementation
  is blocked until 133 (or a same-week follow-up on that spec) routes the caller. Tests that
  still call the method are updated here; production callers are not.
- **Internal persist still needed**: contradiction check, embedding, graph link, and
  `claim_kind` derivation stay on the store. They become private to the seam callback, not a
  second public API with a new name that plugins can call.
- **Unknown leftover dialect values**: if a row is neither `raw`, `synthesized`, nor already
  a doctrine value, migration fails loudly (no silent map to `prompt_supplied`).
- **Quality / feed surfaces**: diagnostics that count `raw` must count doctrine values
  instead. The memory feed's "synthesized" badge remains valid because that enum member
  stays. Do not invent a `raw` badge for `prompt_supplied`.
- **`propose_events` / episodes / entities**: untouched unless a type error appears because
  `Fact.provenance` is no longer `str`. Fix only those compile breaks; do not redesign those
  writes.
- **Dev databases**: wipe and remigrate is expected; no dual-read of old and new provenance.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `Fact` MUST type `provenance` as the shared doctrine `Provenance` enumeration
  (`graph_recall`, `live_search`, `prompt_supplied`, `synthesized`). The string dialect
  `"raw"` / `"synthesized"` on `Fact` MUST be deleted. There MUST NOT be a default of `"raw"`.
- **FR-002**: `memory_facts.provenance` MUST persist only doctrine `Provenance` values,
  required on insert (NOT NULL, no coalescing default of `raw` at read time). Retrieval,
  entity-anchor, and policy SQL that currently `COALESCE(provenance, 'raw')` MUST select
  provenance as stored and MUST NOT invent `raw`.
- **FR-003**: `Fact` MUST carry `claim_kind` as the shared `ClaimKind` enumeration, matching
  the column Phase 111 already added. Load and insert paths MUST round-trip it.
- **FR-004**: Fact confidence MUST continue to use the shared confidence vocabulary: stored
  as a 0–1 value on the row; synthesized uncorroborated rows decay via the shared
  `TIME_LINEAR` function with existing 0.50 / 0.25 cliffs. This phase MUST NOT introduce a
  second decay implementation or a frozen-confidence profile.
- **FR-005**: On insert, provenance MUST be taken from the submitting `Contribution` (133's
  write path) or, for store-internal writers that already persist facts without going through
  a new producer (dream promotion, consolidation merge), from an explicit doctrine
  `Provenance` — never inferred as `"raw"`. Mapping for **existing rows only**: `raw` and
  NULL → `prompt_supplied`; `synthesized` → `synthesized`; values already in the doctrine
  set stay; any other value fails the migration.
- **FR-006**: `propose_facts` MUST be removed from the public `MemoryStore` contract in this
  same phase. Persistence MAY remain as a private method owned exclusively by the
  contribution-seam `write=` callback (or the callback's body). Plugins, graph nodes,
  ingestion, onboarding, and automation MUST NOT import a public fact-write method.
- **FR-007**: If any production caller of `propose_facts` remains after 133, this phase MUST
  NOT add a shim, wrapper, or renamed public alias so that caller keeps compiling. That
  situation is a blocker (see User Story 2, scenario 3). Test-only call sites MAY be rewritten
  here.
- **FR-008**: Write paths that currently branch on `fact.provenance == "synthesized"`
  (including `claim_kind` derivation and corroboration helpers) MUST compare against doctrine
  `Provenance.SYNTHESIZED` (and `ClaimKind` where kind is the real discriminator).
- **FR-009**: The fact-quality diagnostic MUST report counts keyed by doctrine provenance
  values. It MUST NOT report a `raw` bucket.
- **FR-010**: This phase MUST NOT migrate perception call sites (that is 133). It MUST NOT
  change MemorySink extractor plugin contracts except where the `Fact` type change forces a
  field type update. It MUST NOT change PriorityView, turn surfacing, resume recap, loop
  surfacing, contribution arbitration, `signal_sources()` polling, or add action-result
  records as a new producer.
- **FR-011**: Schema change is a hard cut: one migration, no dual-write, no dual-read, no
  deprecated column left beside the new vocabulary. Local and seed databases are expected to
  remigrate.
- **FR-012**: `propose_events`, episode writes, and entity upserts stay as they are unless
  they fail to type-check because they constructed `Fact(..., provenance="raw")`. Those
  constructions MUST be updated to doctrine provenance; the event/episode/entity APIs
  themselves MUST NOT be redesigned.

### Key Entities

- **`Fact`**: a remembered claim about the user or the world. After this phase it carries
  shared `claim_kind`, doctrine `provenance`, and a confidence value that ages with the shared
  decay function when synthesized and uncorroborated.
- **`memory_facts` row**: the persisted form of `Fact`. Provenance column stores only doctrine
  values; `claim_kind` already required since Phase 111.
- **`Provenance` / `ClaimKind` / `Confidence`**: the Phase 111 vocabulary in `ze_agents.claims`.
  This phase does not add enum members. Inflow channel (conversation, email, ingestion) is
  still not a `Provenance` value.
- **Contribution write callback**: the only licensed persist path for new perception facts
  after 133; this phase makes it the only public-facing persist path by deleting
  `propose_facts`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After migration, 100% of `memory_facts` rows have non-null provenance in the
  four-value doctrine set; 0% of rows store `raw`.
- **SC-002**: A newly remembered prompt-supplied fact, retrieved through the same surfaces a
  user or operator already uses (memory retrieval and the fact-quality diagnostic), shows
  `prompt_supplied` rather than `raw` in 100% of those reads.
- **SC-003**: The public memory-store contract contains 0 methods named `propose_facts`.
  Production code outside the memory package's private write callback contains 0 calls to
  `propose_facts`.
- **SC-004**: Synthesized uncorroborated facts still lose confidence on the existing 30-day
  cadence; decay still applies to 100% of rows that would have matched `provenance =
  'synthesized'` before the cut.
- **SC-005**: No second provenance vocabulary remains on `Fact` (no parallel `str` field
  meaning raw/synthesized). Verification: constructing a fact with `provenance="raw"` is a
  type/value error, not a stored dialect.
- **SC-006**: Existing tests for contradiction detection, retrieval, dream decay, and memory
  feed synthesized-badging pass after updates for the new types; no production shim is added
  to keep old tests calling a public `propose_facts`.

## Assumptions

- **133 contract**: [`133-perception-facts-seam`](../133-perception-facts-seam/spec.md) routes
  conversation `write_memory` (extracted vs explicit, stamped per fact), `MemorySink`,
  messenger inbound, onboarding `memory_fact` seeds, and goal-learning promotion (synthesized
  perception facts with the goal as evidence) through `Contribution`. 133 stamps extracted
  conversation/ingestion/inbound facts `SYNTHESIZED` and explicit/onboarding facts
  `PROMPT_SUPPLIED`. This phase persists those doctrine values as-is. This spec does not
  duplicate those call-site tasks.
- **Directory numbering**: this feature is **134**. Spec 5 is **133-perception-facts-seam**.
- **Historical `raw` → `prompt_supplied`**: only a migration backfill for rows that still
  store the old dialect. New writes use 133's per-fact stamps (or explicit doctrine
  provenance on store-internal dream/consolidation writers). Graph-recall and live-search
  remain available when a writer actually recalled or searched.
- **Confidence on the row stays a float**: matching `Signal`. "Use Confidence for real"
  means shared decay math + shared types on kind/provenance, not a new `decay_profile`
  column.
- **Private helper name** is an implementation choice (`_persist_facts`, inlined `write=`,
  etc.) as long as it is not on `MemoryStore` Protocol and not imported by plugins.
- **UI**: memory-feed synthesized badge stays; no product redesign. Fact-quality JSON keys
  change from `raw` to doctrine names (acceptable pre-v1 REST break).
- **Single-user, pre-v1**: no production cutover; seed wipe is expected.
- **Out of scope confirmed**: contribution arbitration (rollout step 8), action-result
  records as a new producer (step 7) except finishing whatever 133 already routed, Priority
  View / Phase 132, `signal_sources()` consumer rewiring, MemorySink extractor redesign.
