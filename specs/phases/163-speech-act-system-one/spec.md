# Feature Specification: Speech-Act System One

**Feature Branch**: `163-speech-act-system-one`

**Created**: 2026-09-30

**Status**: Implemented (surface ships off; bars await calibration)

**Input**: User description: "Replace the Haiku speech_act + keep/drop judge with System One Choice over the existing closed set, plus family Choice and biography Noul. Keep admit_* filters, trivial-turn regex, dual-write skip, contribution seam. Depends on 162. Do not start routing Choice (164)."

**Governed by**: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O1, [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Phases [140](../140-memory-admission/spec.md)–[148](../148-extractor-dual-write/spec.md), especially 142 routing table and 148 “hard classifier later.”

**Depends on**: Phase [162](../162-system-one-client/spec.md) Implemented.

**Does not start**: Routing Choice (164); skill suggestion; loop extraction Noul; in-turn companion tool rewrite beyond consuming the same labels.

---

## Overview

Every non-trivial conversation turn asks a generative model to emit JSON `{speech_act, family, facts[]}`. Code already knows the closed sets and already drops unknown labels. Phase 148 kept that LLM judge and deferred a hard classifier.

This phase **replaces the judge**, not the store rules. The eight speech acts and the keep/drop families stay exactly those sets. If the judgment service is skipped, Haiku (or the current extractor) remains the fallback — fail open, no dual-write of two facts.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A timed reminder is not stored as biography (Priority: P1)

The user says they want a ping at a time (“remind me Tuesday,” “remember to call Mom at 3”). The admission path labels that as reminder (or drop), not fact. No biography row is written from extraction.

**Why this priority**: This is the honesty failure 142 exists to stop. The LLM judge still gets it wrong.

**Independent Test**: Fixture user+assistant text with gold `speech_act=reminder`; persist path writes zero biography facts. Existing `memory_speech_act_*` scenarios still pass.

**Acceptance Scenarios**:

1. **Given** a timed remind utterance, **When** post-turn admission runs with System One available, **Then** `speech_act` is `reminder` and `facts` is empty.
2. **Given** “remember to …” with a time, **When** admission runs, **Then** time still wins over biography (142 R11): not `fact`.
3. **Given** a durable preference (“I prefer aisle seats”) with no time, **When** admission runs, **Then** `speech_act` is `fact` and family is a keep family.

---

### User Story 2 - Cancel language is not forget-biography (Priority: P1)

The user says “forget the dentist” meaning cancel a reminder. Admission labels reminder (or loop/goal), never `forget`, unless the utterance is clearly retracting a standing preference.

**Why this priority**: Phase 146. The eight-way Choice must include both `forget` and `reminder` with criteria that separate them.

**Independent Test**: Two fixtures: aisle-seat retract vs dentist-cancel. Gold acts `forget` vs `reminder`.

**Acceptance Scenarios**:

1. **Given** biography retract wording, **When** admission runs, **Then** `speech_act` is `forget` and no new fact is admitted.
2. **Given** cancel-the-ping wording, **When** admission runs, **Then** `speech_act` is not `forget`.
3. **Given** an unknown label from a buggy client, **When** `admit_speech_act` runs, **Then** the act is `drop` (existing fail-safe).

---

### User Story 3 - Unsure does not silently persist (Priority: P2)

The closed-set answer is spread across several labels, or the yes-probability that this is durable biography is near even. Code does not persist a fact “because something had to be chosen.”

**Why this priority**: Choice without a `drop`/`clarify` path would pick the closest label. Doctrine: silent wrong admit is worse than missing a fact.

**Independent Test**: Fake client returns a near-uniform distribution or a biography Noul near 0.5; persist writes no fact.

**Acceptance Scenarios**:

1. **Given** a Choice peakedness below the (this-phase, measured) hold bar, **When** admission would otherwise persist, **Then** it persists nothing (or falls back to Haiku only if skip, not if “unsure”).
2. **Given** biography Noul near even and Choice `fact`, **When** composing, **Then** code MUST NOT persist on Choice alone.
3. **Given** System One skip (timeout), **When** admission runs, **Then** the pre-163 extractor path runs once — not both judges writing two rows.

---

## Edge Cases

- Trivial greetings: existing regex skip; do not call System One.
- Assistant text already truncated: do not send full session history.
- Portuguese reminders: criteria MUST include PT examples or equivalent; do not assume English-only accuracy.
- In-turn `remember_fact` `ok` true: dual-write skip (148) still wins over extraction.
- Contribution seam still rejects illegal kinds; this phase does not write `INFERENCE` as biography.
- Option order: production order is stable (doctrine / existing enum order); eval MAY shuffle.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Post-turn admission MUST obtain `speech_act` as a Choice over exactly `fact`, `forget`, `reminder`, `loop`, `goal`, `ingest`, `drop`, `clarify`.
- **FR-002**: When the act may be `fact`, admission MUST also obtain a family Choice over the existing keep families plus `drop`, and a separate biography yes-probability. The yes-probability threshold MUST NOT be copied from Choice peakedness.
- **FR-003**: Existing `admit_speech_act` and `admit_family` MUST remain the only persist filters for labels. Unknown → drop.
- **FR-004**: Facts MUST persist only when act is `fact`, family is a keep family, and the biography yes-probability clears a hold bar measured on Ze fixtures. Otherwise `facts` is empty.
- **FR-005**: State MUST be `{user text, assistant text}` (assistant already length-capped). MUST NOT send the full session or memory tables.
- **FR-006**: On System One skip, the current LLM extractor MUST run as today. On a low-peakedness **answer**, MUST NOT persist and MUST NOT also run Haiku to “break the tie” in this phase (avoid double judges).
- **FR-007**: Trivial-turn skip, 148 same-turn identity skip, and contribution-seam writes MUST remain.
- **FR-008**: This phase MUST NOT change routing, skill match, or companion tool names. Companion instructions MAY keep teaching the same eight acts.
- **FR-009**: Default tests MUST mock the judgment client. Eval scenarios that already forbid a fact row MUST still forbid it.
- **FR-010**: Thresholds MUST live in config under the System One surface flags, documented as uncalibrated until measured — cookbook numbers MUST NOT ship as production defaults.

### Key Entities

- **Speech act**: One of the eight labels already on `SpeechAct`.
- **Keep family**: identity, preference, relationship, constraint, contact_detail.
- **Hold**: Low peakedness or middling biography probability → no persist.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing speech-act evals that require no biography row still show no biography row with System One on (mocked gold).
- **SC-002**: Dentist-cancel vs aisle-forget fixtures disagree on `forget` vs `reminder` in the gold direction 100% of the labeled pair.
- **SC-003**: 0 turns persist a fact when biography yes-probability is in the even band (fixture-defined).
- **SC-004**: Skip path: 0 duplicate fact rows vs Haiku-only on the same identity.
- **SC-005**: 0 live vendor calls in default `make test-memory` / personal tests for this change.

---

## Assumptions

- 162 is Implemented before this work starts.
- In-turn `delegate_to_agent` / remember tools stay the conversational path; this phase owns **post-turn persist**.
- Hold bars are chosen at implement from fixtures, not invented in this spec as floats.
- English-primary model: PT fixtures are required before enabling for a Portuguese-heavy user.

## Out of Scope

- 164 routing.
- Hard-coupling post-turn act to in-turn tools (measure disagreement first — arch open question).
- Loop/goal/reminder **creation** from this judge (142 already routes tools; this only stops fact persist).
- Replacing write-time NLI.

## Verbatim Constraints

- `speech_act`
- `fact`
- `forget`
- `reminder`
- `loop`
- `goal`
- `ingest`
- `drop`
- `clarify`
- `admit_speech_act`
- `admit_family`
- `SpeechAct`
- `KEEP_FAMILIES`
- `SystemOneClient`
