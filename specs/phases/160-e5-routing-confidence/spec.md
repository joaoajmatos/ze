# Feature Specification: E5 Routing Confidence

**Feature Branch**: `160-e5-routing-confidence`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Specs for Embedding E5 (97): Router still leans on Haiku because MiniLM scores are too low. 153/155 are routing. Better embeddings make conductor rewrite less dependent on decompose."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/local-embeddings.md`](../../arch/local-embeddings.md), constitution Principle VII, Phase 97 [`097-embedding-model-upgrade`](../097-embedding-model-upgrade/spec.md), sequential/mixed routing [`153-sequential-routing-hard-cut`](../153-sequential-routing-hard-cut/spec.md) / [`155-mixed-gather-act-conductor`](../155-mixed-gather-act-conductor/spec.md).

**Depends on**: Phase 97 model swap (already in tree: `E5Embedder`, `intfloat/multilingual-e5-base`, query/passage prefixes). 153/155 conductor rewrite stays as-is.

**Does not start**: A second embedding model; restoring MiniLM; changing conductor rewrite or deleting Haiku decompose for true ambiguity; 159 thread identity.

---

## Overview

Phase 97’s **model is already live**: routing and memory share `intfloat/multilingual-e5-base` with query/passage prefixes. What 97 explicitly deferred is **confidence**: the router still uses MiniLM-era bars (`ROUTING_THRESHOLD` 0.55, default `ROUTING_GAP` 0.10). E5 scores sit in a tight high band, so a MiniLM-sized gap still marks ordinary single-job messages as compound. Those turns go to Haiku decompose, and 153/155 then rewrite many of them to the conductor.

This phase calibrates confidence to E5 so a clear calendar (or mail, or research) question goes to that specialist without a decompose hop. True mixed or sequential jobs still decompose and still hit 153/155. Living docs that still name MiniLM are hard-cut. The model is not swapped again.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A clear single job does not call the fallback planner (Priority: P1)

The user asks one specialist to do one thing (“what’s on my calendar tomorrow”, “send this to Ana”). The router is confident. The turn does **not** go through Haiku decompose. Conductor rewrite never sees a fake compound plan.

**Why this priority**: 153/155 only rewrite envelopes that look compound. False compounds make every ordinary question look like a conductor job.

**Independent Test**: Fixture scores in E5’s observed band for a clear winner: `is_compound` is false under production defaults. A MiniLM-era 0.10 gap MUST NOT be the production default.

**Acceptance Scenarios**:

1. **Given** a clear single-agent prompt whose top score and gap meet the E5-calibrated bars, **When** routing runs, **Then** the envelope is embedding-only, not compound, and Haiku decompose is not invoked.
2. **Given** production defaults with no YAML overlay, **When** the router is constructed, **Then** threshold and gap are the E5-calibrated values (YAML may match them; it MUST NOT be the only place they exist).
3. **Given** 153/155 rewrite rules, **When** a turn is a true single specialist, **Then** companion is not injected as conductor solely because of a MiniLM-sized gap.

---

### User Story 2 - Real mixed or sequential work still decomposes (Priority: P1)

The user asks two jobs that actually need a plan (“research X then email Y”). Scores are close or the prompt is mixed. Haiku decompose still runs. 153/155 still rewrite sequential/mixed envelopes to companion. Independent multi-read still fans out.

**Why this priority**: Calibrating confidence must not silently kill decompose. Conductor still needs a hint on genuine multi-job turns.

**Independent Test**: Low gap or below-threshold fixtures still set `is_compound`. Existing 153/155 rewrite tests still pass unchanged.

**Acceptance Scenarios**:

1. **Given** two specialists with a gap below the E5-calibrated gap bar, **When** routing runs, **Then** the envelope is compound and decompose still owns the fallback.
2. **Given** a sequential or mixed gather+act envelope from decompose, **When** 153/155 rewrite runs, **Then** companion is still primary (no change to those phases).
3. **Given** independent multi-read that remains compound and not sequential, **When** the graph runs, **Then** fan-out + synthesize still happens (155/158 unchanged).

---

### User Story 3 - The product says E5, not MiniLM (Priority: P2)

A new contributor reading the constitution, the local-embeddings ADR, and the stack table sees `intfloat/multilingual-e5-base`. MiniLM is history, not the live model.

**Why this priority**: Principle VII and AGENTS still name MiniLM while code loads E5. That is index dishonesty (same class of bug as 150).

**Independent Test**: Grep of living docs (constitution, ADR, AGENTS/CLAUDE stack table, `docs/architecture.md`, `specs/core/ze-core.md`) has no claim that MiniLM is the current singleton.

**Acceptance Scenarios**:

1. **Given** Principle VII, **When** it names the local embedding model, **Then** it names E5-base (with query/passage prefixes), not MiniLM.
2. **Given** the local-embeddings ADR, **When** a reader checks the decision outcome, **Then** the current choice is E5; MiniLM is a superseded option.
3. **Given** historical phase specs (001, 037, …), **When** this phase ships, **Then** they MAY stay as written; living docs MUST NOT.

---

## Edge Cases

- YAML `routing.gap_threshold: 0.03` already exists as a local overlay: production defaults MUST absorb the calibrated pair so tests and a missing YAML block do not revert to MiniLM 0.10.
- E5 scores compress (observed ~0.73–0.86): raising the **floor** may be required so a mediocre 0.55 match is not “confident.” The implementer measures; this spec does not invent the float.
- Portuguese and English clear matches both skip decompose (97 goal; do not regress).
- Prefixes (`query:` / `passage:`) stay mandatory; a test already owns that — do not drop them while retuning.
- Slow real-model eval (clear single-agent hit rate) is `@pytest.mark.slow`; unit tests use fixtures, never a live model.
- Memory retrieval floors (phase 106) are out of this phase unless a shared default would break them — do not retune memory cosine floors here.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Framework routing defaults (`ROUTING_THRESHOLD`, `ROUTING_GAP`) MUST be calibrated to E5’s score distribution so a clear single-agent match does not set `is_compound`. MiniLM 0.55 / 0.10 MUST NOT remain the code default.
- **FR-002**: YAML MAY repeat the same pair; it MUST NOT be the only source of E5 calibration. A router with no YAML overlay MUST use the E5 defaults.
- **FR-003**: Turns that fail the E5 confidence test MUST still set `is_compound` and still use Haiku decompose. This phase MUST NOT delete decompose.
- **FR-004**: Phases 153 and 155 (`apply_conductor_rewrite`, sequential/mixed rules) MUST NOT change. Fewer false compounds is how conductor rewrite is used less — not a rewrite of those rules.
- **FR-005**: This phase MUST NOT swap the embedding model, MUST NOT restore MiniLM, MUST NOT add a second embedder for routing vs memory.
- **FR-006**: Living documentation (constitution Principle VII, local-embeddings ADR, AGENTS/CLAUDE stack table, `docs/architecture.md`, `specs/core/ze-core.md`) MUST name `intfloat/multilingual-e5-base` as the current local model. Historical phase specs MAY keep MiniLM as written.
- **FR-007**: Clear single-agent fixtures in English and Portuguese MUST route by embedding without decompose under the new defaults. Ambiguous/close-score fixtures MUST still decompose.

### Key Entities

- **Clear single-agent match**: One specialist is the obvious owner; E5 top score and gap clear the calibrated bars.
- **False compound**: MiniLM-era bars marking an ordinary single job as `is_compound`.
- **True compound**: Close scores or mixed/sequential jobs that still need Haiku decompose as a hint.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tested clear single-agent fixtures (EN + PT) leave `is_compound` false under production defaults.
- **SC-002**: 100% of tested below-bar / low-gap fixtures still set `is_compound`.
- **SC-003**: 0 changes to 153/155 rewrite tests’ expected companion-primary cases except those that were false compounds from MiniLM-sized gaps.
- **SC-004**: 0 living-doc claims that MiniLM is the current embedding singleton.
- **SC-005**: Phase 97 index row records model shipped; this directory owns threshold/docs remainder.

---

## Assumptions

- E5-base stays; `e5-small` is not this phase (97 already allowed a config-only swap later).
- Observed compression (~0.73–0.86) from the YAML comment is the starting measurement; implement may adjust both floor and gap together.
- 70%+ of real single-agent messages without Haiku (97 goal) is the north star; unit fixtures prove the bar; a slow eval MAY measure live E5 but is not a release blocker if marked slow.
- Memory embedding quality is already on E5; this phase does not re-null vectors.

## Out of Scope

- Concurrent thread identity (159).
- Changing conductor rewrite, stall, promote, or parallel gates.
- Fine-tuning E5; hosted embedding APIs.
- Memory relevance floors (106) unless a shared constant would break them.

## Verbatim Constraints

- `ROUTING_THRESHOLD`
- `ROUTING_GAP`
- `intfloat/multilingual-e5-base`
- `is_compound`
- `decompose`
- `query:`
- `passage:`
- Principle VII
- Principle VIII
