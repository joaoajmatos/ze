# Feature Specification: Extractor Dual-Write and Dedup Races

**Feature Branch**: `148-extractor-dual-write`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Admission speech_act is still LLM JSON. Post-turn extraction can duplicate in-turn remember_fact. This spec is RACES/DEDUP only. Hard non-LLM speech-act classifier is OUT OF SCOPE (later L). Tests must distinguish model-lied (143) from extractor-duplicated."

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual door), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md) item 148 (races only). Depends on Phase 140 (admission `speech_act` + `remember_fact`) and Phase 143 (tests already know unearned model claims). Plugin code imports `ze_sdk` / `ze_personal` when it must change plugins; engine/memory work stays in those packages — never import `ze_core` from plugins.

---

## Overview

The user can `remember_fact` in the turn. After the reply, extraction can still propose the same fact. Phase 140 allows extraction when predicates dedup; races still create silent duplicates or a second write that looks like a new memory. Admission `speech_act` is still LLM JSON — **replacing that classifier is not this spec**.

This phase closes dual-write and dedup races only. Tests must show a **model lie** (143: confirmation without `ok`) as a different failure from an **extractor duplicate** (second store write of the same in-turn remember). No shim that “sometimes extracts, sometimes doesn’t” without a single rule.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - In-turn remember is not extracted again (Priority: P1)

The user asks Ze to remember a durable fact. `remember_fact` succeeds. Post-turn extraction must not write a second current fact for the same predicate/value (or equivalent identity). The user does not see two memories of one utterance.

**Why this priority**: Duplicate writes are the race; classifier replacement can wait.

**Independent Test**: Successful `remember_fact` then run extraction on the same turn text. Assert one current fact, not two. A 143-style test where the model claims remember without `ok` still fails on the reply, not on a duplicate row.

**Acceptance Scenarios**:

1. **Given** `remember_fact` `ok` true for a fact this turn, **When** post-turn extraction runs on that turn, **Then** it does not persist a second current fact for the same identity.
2. **Given** `remember_fact` was not called, **When** extraction admits a gated fact, **Then** that write may still occur (this phase does not kill extraction).
3. **Given** `remember_fact` `ok` false, **When** extraction would admit a similar fact, **Then** admission/dedup rules still apply; a failed tool is not a license to silently write the same claim as a second door without the 140 gate.

---

### User Story 2 - Tests name the failure (Priority: P1)

A test that the model said “I’ll remember” without `ok` is a **143 model-lie** case. A test that two store writes exist after one remember is an **extractor-duplicate** case. They MUST NOT be the same assertion.

**Why this priority**: The roadmap’s reason to wait for 143 was exactly this distinction.

**Independent Test**: Two fixtures. Lie fixture: no successful tool, reply gated, store may be empty. Duplicate fixture: successful tool plus extraction; store has one current fact. Failure messages / test names distinguish them.

**Acceptance Scenarios**:

1. **Given** a model-lie fixture (confirmation language, no `remember_fact` `ok`), **When** tests run, **Then** they assert reply honesty (143), not “extractor wrote twice.”
2. **Given** a duplicate-race fixture (tool `ok` plus extraction), **When** tests run, **Then** they assert at most one current fact for that identity, not “the model lied.”
3. **Given** this phase ships, **When** a developer reads the tests, **Then** there is not one overloaded check that conflates the two.

---

### User Story 3 - One write rule, no classifier rewrite (Priority: P2)

Dedup/race handling is a single product rule (same identity cannot be current twice from the same turn’s remember + extract). The LLM `speech_act` classifier remains. A parallel “extract anyway” path that ignores the rule is a dual door.

**Why this priority**: Principle VIII; keep the later L classifier out.

**Independent Test**: Documented identity for “same fact” (predicate + value, or existing 140 identity). No new non-LLM speech-act classifier module shipped as this feature.

**Acceptance Scenarios**:

1. **Given** this phase, **When** extraction and `remember_fact` both see the same utterance, **Then** one current fact remains (dedup or skip extract).
2. **Given** this phase, **When** the catalog of work is reviewed, **Then** no hard non-LLM speech-act classifier was added.

---

## Edge Cases

- Two different predicates, same value: not automatically the same identity (do not over-collapse).
- Same predicate, trivially different punctuation/casing: treat as the same identity when 140 already would.
- Extraction runs when remember succeeded for a **different** fact in the same turn: extract may still admit the other fact.
- Concurrent turns: this spec covers same-turn remember then extract; cross-turn duplicates stay on existing fact identity/dedup unless they are the same race class (Assumption: same-turn is in scope; global merge is not a new product).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST prevent post-turn extraction from persisting a second current fact for the same identity as a successful in-turn `remember_fact` on that turn.
- **FR-002**: System MUST keep extraction available for turns that did not already remember that identity via `remember_fact`.
- **FR-003**: Tests MUST distinguish Phase 143 model-lie (unearned confirmation / no `ok`) from extractor-duplicated writes (two currents after one remember).
- **FR-004**: System MUST NOT ship a hard non-LLM speech-act classifier in this phase.
- **FR-005**: System MUST NOT leave a second extract path that ignores FR-001 (no shim).
- **FR-006**: Plugin changes MUST import `ze_sdk` / `ze_personal`, never `ze_core`.
- **FR-007**: This phase MUST NOT implement 144 veto, recitation, forget-vs-cancel, ingest copy as a bundle, specialist constitution, or a `/memories` filesystem.

### Key Entities

- **Fact identity**: The 140 notion of the same biography fact (predicate and value, after existing normalization).
- **In-turn remember**: Successful `remember_fact` (`ok` true) during the agent turn.
- **Post-turn extraction**: LLM JSON admission after the reply (`speech_act` still model-produced).
- **Model-lie**: User-visible remember confirmation without `ok` (Phase 143).
- **Extractor duplicate**: A second current row for an identity already written this turn.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested turns with `remember_fact` `ok` true for an identity, post-extraction current count for that identity is 1.
- **SC-002**: In 100% of tested model-lie fixtures, tests fail on reply claims, not on duplicate-row counts.
- **SC-003**: In 100% of tested duplicate-race fixtures, tests fail on extra current facts, not on reply wording.
- **SC-004**: The shipped work includes zero new hard speech-act classifier.

---

## Assumptions

- “Same identity” reuses Phase 140 predicate/value identity, not a new embedding merge.
- `speech_act` remains LLM JSON; improving JSON schema is allowed only if it serves dedup, not a classifier rewrite.
- `write_memory` / extractor live in core memory/engine; this spec does not move them into plugins.
- Failed `remember_fact` does not uniquely imply extraction should write; 140 admission still applies.

## Out of Scope

- Hard (non-LLM) speech-act classifier (later L).
- Constraint veto (144), recitation (145), forget-vs-cancel (146), ingest honesty (147) as bundles.
- Specialist constitution (149).
- Claude-style `/memories` filesystem.
- Rewriting 140–142 write/read/routing contracts as a bundle.

## Verbatim Constraints

- `speech_act`
- `remember_fact`
- `ok`
- Principle VIII (no shim, no dual door)
- `ze_sdk`
- `ze_core`

## After this feature / Future work

Hard non-LLM speech-act classifier (roadmap L). Then 149 specialists, 150 eval+guides. See [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md).
