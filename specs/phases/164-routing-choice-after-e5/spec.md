# Feature Specification: Routing Choice After E5

**Feature Branch**: `164-routing-choice-after-e5`

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: "Complement EmbeddingRouter with System One Choice over the E5 shortlist plus none, and a complexity Score. Keep E5 encode, 160 bars as shortlist, Haiku decompose when none/low confidence/multi-specialist. Do not change 153/155. Depends on 162. Do not start in the 163 tree."

**Governed by**: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O2, [`specs/arch/local-embeddings.md`](../../arch/local-embeddings.md), [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Phases [160](../160-e5-routing-confidence/spec.md), [153](../153-sequential-routing-hard-cut/spec.md), [155](../155-mixed-gather-act-conductor/spec.md).

**Depends on**: Phase [162](../162-system-one-client/spec.md) Implemented. Phase 160 Implemented (E5 bars stay the shortlist).

**Does not start**: Speech-act (163) in this tree; skill suggestion; deleting Haiku decompose; changing conductor rewrite.

---

## Overview

Phase 160 made E5 cosine bars honest enough that clear singles skip Haiku. The envelope still stores **cosine as `confidence`**. Low score or low gap still means `is_compound` and Haiku decompose — including some turns that are one specialist with a close runner-up description.

This phase keeps E5 as the **shortlist**. A typed Choice over those agents plus `none` decides whether to trust a single specialist. A graded complexity question replaces the regex word-count classifier for model tiering. True mixed/sequential work still decomposes; 153/155 still rewrite those envelopes.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A clear single job still skips the fallback planner (Priority: P1)

The user asks one specialist to do one thing. E5 already has a clear top. The Choice agrees. Haiku decompose is not invoked. Envelope `confidence` on the explainability surface is the Choice peakedness (or both scores are stored — cosine MUST NOT be the only “confidence” shown as if calibrated).

**Why this priority**: Must not regress 160.

**Independent Test**: 160 clear-single fixtures (EN+PT) still have `is_compound` false when the fake Choice returns that agent with high peakedness.

**Acceptance Scenarios**:

1. **Given** a 160-style clear calendar prompt, **When** routing runs with System One available and Choice = calendar at high peakedness, **Then** the envelope is embedding-path, not compound, and decompose is not called.
2. **Given** System One skip, **When** routing runs, **Then** 160 cosine bars apply unchanged.
3. **Given** the Mind / trace view, **When** a Choice was consumed, **Then** the user-visible confidence is not solely the raw cosine labeled as if it were doctrine confidence.

---

### User Story 2 - Close scores can still be one specialist (Priority: P1)

E5 gap is under the 160 gap bar (would have decomposed) but Choice picks one agent with high peakedness and `none` is low. The turn does not go to Haiku.

**Why this priority**: This is the cost/latency win: fewer false compounds.

**Independent Test**: Fixture with top two agents close in cosine; fake Choice returns agent A at high peakedness; `is_compound` is false.

**Acceptance Scenarios**:

1. **Given** cosine gap below the 160 gap bar, **When** Choice selects one shortlisted agent with peakedness above the (measured) act bar, **Then** decompose is not invoked.
2. **Given** the same cosine gap, **When** Choice is `none` or peakedness is low, **Then** decompose still runs (160 FR-003 preserved as fallback).
3. **Given** Choice `none` with high peakedness, **When** routing completes, **Then** decompose runs even if cosine looked like a clear top (model refuses the shortlist).

---

### User Story 3 - Real mixed work still decomposes; conductor rewrite unchanged (Priority: P1)

Two jobs that need a plan still become compound. Sequential/mixed still rewrite to companion. Complexity Score only picks simple vs complex **model**, not which agents.

**Why this priority**: Conductor roadmap pin: Haiku is a hint, not deleted.

**Independent Test**: 153/155 tests still pass. A mixed gather+act fixture still decomposes when Choice `none` or a multiple-specialist yes-probability is high.

**Acceptance Scenarios**:

1. **Given** a sequential or mixed gather+act prompt, **When** the multiple-specialist yes-probability is high or Choice is `none`, **Then** `is_compound` is true and decompose still owns the hint.
2. **Given** a compound sequential envelope from decompose, **When** 153/155 rewrite runs, **Then** companion is still primary (no change to those phases).
3. **Given** a lookup-style prompt, **When** complexity Score is at the low (lookup) end with high peakedness, **Then** the simple model tier is used; this MUST NOT force a different agent.

---

## Edge Cases

- Shortlist size: code picks top-k from E5 (k small, complete coverage). An omitted agent cannot be chosen — if the right agent is outside k, Choice should be `none` → decompose.
- Single enabled agent: keep today’s confidence-1 envelope; do not call System One.
- History hint: keep existing truncation; do not send full transcript.
- Option-name bias: criteria are agent **descriptions**, keys are agent names; keep descriptions aligned with `@agent.description`.
- Regex complexity: on skip, keep `ComplexityEstimator` as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: E5 encoding and 160 threshold/gap MUST still produce a ranked list. System One MUST see only a shortlist plus `none`, not the whole roster as unbounded generation.
- **FR-002**: When System One is consumed, single-agent routing MUST follow Choice: a shortlisted agent at sufficient peakedness → not compound; `none` or low peakedness → existing decompose path.
- **FR-003**: A separate yes-probability for “needs more than one specialist” MAY be asked in the same request (speculative). It MUST only be read when deciding decompose, and MUST NOT use the Choice peakedness threshold.
- **FR-004**: Complexity MUST be a graded Score with descriptive levels (lookup / single tool / multi-hop). Word-count regex remains the skip fallback. Score MUST NOT invent a numeric word count.
- **FR-005**: Phases 153 and 155 MUST NOT change. Decompose MUST NOT be deleted.
- **FR-006**: On skip, behavior MUST match 160 exactly.
- **FR-007**: Trace MUST record Choice, `none` probability, complexity Score, and whether decompose ran; cosine raw scores MAY remain as `raw_scores`.
- **FR-008**: Clear single-agent EN and PT fixtures from 160 MUST still skip decompose when Choice agrees.
- **FR-009**: This phase MUST NOT change speech-act admission (163), skills, or capability modes.
- **FR-010**: Default tests MUST mock the judgment client.

### Key Entities

- **Shortlist**: Top E5 agents (closed set for Choice) plus `none`.
- **False compound**: 160 would decompose; Choice says one agent.
- **True compound**: Choice `none` or high multiple-specialist probability; decompose + 153/155 as today.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of 160 clear-single EN+PT fixtures still skip decompose when Choice agrees with the E5 winner at high peakedness.
- **SC-002**: At least one close-gap fixture skips decompose under Choice-high that would have decomposed under 160 bars alone.
- **SC-003**: 100% of 153/155 rewrite tests keep companion-primary expectations for true sequential/mixed envelopes.
- **SC-004**: Skip/disabled: 0 differences vs 160 on routing unit fixtures.
- **SC-005**: 0 live vendor calls in default routing tests.

---

## Assumptions

- 162 Implemented. 163 may be specified in parallel but is not a dependency.
- k and act/hold bars are measured at implement (start from 160’s observed E5 band and a small k, e.g. 3–5).
- Intent on the embedding path may remain “first listed intent” in this phase; Choice of **intent** is out of scope unless it falls out of decompose.

## Out of Scope

- Deleting Haiku decompose.
- Changing conductor caps, stall, or promote.
- Skill matching (O3).
- Routing on images without the existing caption step (Jev is text-only).

## Verbatim Constraints

- `EmbeddingRouter`
- `ComplexityEstimator`
- `is_compound`
- `decompose`
- `none`
- `ROUTING_THRESHOLD`
- `ROUTING_GAP_THRESHOLD`
- `SystemOneClient`
- `apply_conductor_rewrite`
- `raw_scores`
