# Feature Specification: Ingest vs Remember Honesty

**Feature Branch**: `147-ingest-remember-honesty`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "File ingest still writes synthesized facts via MemorySink; model must not talk as if remember_fact ran. Ingest/companion copy and eval. 143 only gates companion tool ok."

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual door), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), Phase 142 **R7**, [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md) item 147. Depends on Phase 133 (`MemorySink` synthesized perception facts) and Phase 143 (companion remembered claims gated on `remember_fact` `ok` only). Plugin code imports `ze_sdk` / owning plugin, never `ze_core`.

---

## Overview

When the user ingests a file, Ze may write synthesized perception facts through `MemorySink`. That is not `remember_fact`. Phase 143 only stops companion from saying “I’ll remember” without that tool’s `ok`. After a PDF ingest, the model can still talk as if the remember tool ran.

This phase fixes ingest and companion copy and eval so file ingest is not confirmed as a remember-tool success. It does not change the sink write path into a second remember API.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest is not “I’ll remember that” (Priority: P1)

The user asks Ze to read or ingest a document. Facts may land via `MemorySink`. The user-visible reply must not claim the remember tool stored a biography fact. It may say the file was ingested or that document facts were extracted, without borrowing remember-tool success language.

**Why this priority**: Mixing ingest with remember is the R7 honesty lie.

**Independent Test**: Drive ingest of a document. Model output claims “I’ll remember that” / `remember_fact` success. User-visible copy and eval graders treat that as a fail unless `remember_fact` actually returned `ok` true this turn (it should not, for ingest-only).

**Acceptance Scenarios**:

1. **Given** a file ingest turn with `MemorySink` writes and no `remember_fact` `ok` true, **When** Ze replies, **Then** the user-visible text does not claim the remember tool succeeded.
2. **Given** ingest completed, **When** Ze replies, **Then** it may describe ingest/extraction in ingest language, not as a biography remember confirmation.
3. **Given** the user both ingests a file **and** separately asks to remember a standing preference in the same turn, **When** `remember_fact` `ok` is true for that preference, **Then** confirmation is allowed only for that remembered fact, not for the file as a whole.

---

### User Story 2 - Eval does not reward the mix-up (Priority: P2)

Graders and scenarios that still treat ingest success as remember-tool success are hard-cut. There is no dual standard.

**Why this priority**: Tests that score the old lie will keep it.

**Independent Test**: Eval fixtures for ingest must fail if the assistant claims `remember_fact` success without that tool `ok`. Fixtures must pass honest ingest acknowledgements.

**Acceptance Scenarios**:

1. **Given** an ingest eval scenario, **When** the assistant claims remember-tool success without `remember_fact` `ok`, **Then** the scenario fails.
2. **Given** this phase ships, **When** judges look for remember vs ingest, **Then** they use `tool_calls` / ingest outcome, not a leftover proposals count.

---

## Edge Cases

- Ingest fails: do not claim ingest **or** remember success.
- Empty extraction (file stored, zero facts): do not claim facts were remembered.
- Companion discusses the document contents: allowed as reading, not as “I’ll remember that” unless `remember_fact` `ok`.
- Streaming: final visible reply follows the same rule.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST NOT present file ingest / `MemorySink` writes as `remember_fact` success. Remembered confirmations remain gated on `remember_fact` `ok` true (Phase 143).
- **FR-002**: Ingest and companion user-visible copy MUST describe ingest as ingest (or document extraction), not as the remember tool.
- **FR-003**: Eval scenarios and graders that currently treat ingest as remember-tool success MUST be hard-cut (no dual standard).
- **FR-004**: This phase MUST NOT replace `MemorySink` with `remember_fact`, add a new remember API, or implement Phase 144 veto, recitation, forget-vs-cancel, extractor races, specialist constitution as a bundle, or a `/memories` filesystem.

### Key Entities

- **Ingest write**: Synthesized perception facts from `MemorySink` (Phase 133), not biography remember-tool success.
- **Remember-tool success**: `remember_fact` returning `ok` true this turn.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested ingest-only turns with no `remember_fact` `ok`, graders find zero remember-tool success claims.
- **SC-002**: In 100% of tested ingest eval fixtures, honest ingest acknowledgements pass and remember-tool claims without the tool fail.
- **SC-003**: After this phase, there is a single product rule: ingest is ingest; remember confirmations require the remember tool.

---

## Assumptions

- `MemorySink` continues to write synthesized cited facts; this spec is copy, reply honesty, and eval, not a sink redesign.
- Companion remains the usual speaker after ingest when the user asked in chat; ingest jobs that never speak still must not emit remember-tool copy if they notify.
- Phase 143 gate may already strip “I’ll remember” without `ok`; this phase still fixes remaining ingest-specific copy and eval that 143 did not cover.

## Out of Scope

- Constraint veto on gated writes (Phase 144).
- Unsolicited recitation (Phase 145) except overlapping remember-tool wording already covered by 143/this copy rule.
- Forget vs cancel (Phase 146).
- Extractor dual-write races (Phase 148).
- Specialist constitution (Phase 149).
- Deleting `memory_proposals_count` (Phase 150) except not relying on it here.
- Claude-style `/memories` filesystem.

## Verbatim Constraints

- `MemorySink`
- `remember_fact`
- `ok`
- R7
- Principle VIII (no shim, no dual door)
- `ze_sdk`
- `ze_core`

## After this feature / Future work

See [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md). Next: 148 extractor races, 149 specialists, 150 eval+guides.

## Approach

- Audit ingest and companion user-visible copy so ingest acknowledgements cannot read as `remember_fact` success.
- Extend the 143 reply honesty rule (or ingest-specific eval) so ingest-only turns cannot confirm remember-tool success.
- Hard-cut eval fixtures that reward the mix-up. Do not redesign `MemorySink` or add remember tools.
