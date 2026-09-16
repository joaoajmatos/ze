# Feature Specification: Conductor Observability and Eval

**Feature Branch**: `154-conductor-observability-eval`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "154 Conductor observability and eval: Trace panel: plan, specialist, confirmation ids. Progress keys. Eval scenarios: sequential dependent; independent parallel not via companion; speech-act still 146-honest; mid-sequence confirmation resumes next specialist."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md) phase 154, [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`153-sequential-routing-hard-cut`](../153-sequential-routing-hard-cut/spec.md) ledger fields, [`152-per-delegate-gate`](../152-per-delegate-gate/spec.md), [`146-forget-vs-cancel`](../146-forget-vs-cancel/spec.md).

**Depends on**: 153 ledger on `MessageTrace`; 152 `request_id`; 151 nested `tool_calls`.

**Does not start**: Promote to workflow/goal; stall Magentic outer loop; parallel graph per-subtask gates.

---

## Overview

After 153, mixed turns run through companion, but the user can still see a mute wait and the trace panel can still look like a single agent with opaque tools. This phase makes the sequence visible and makes the routing claims testable.

The trace (side) panel shows the conductor plan/hint, each specialist, confirmation ids, and stall/ask. Progress text uses keys so the user sees “checking calendar…” then “drafting the mail…”. Eval scenarios lock: dependent calendar-then-email goes through companion with the event id in the next brief; independent parallel does **not** go through companion; speech-act one-shots stay 146-honest; a confirmation in the middle resumes the next specialist.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trace shows the sequence (Priority: P1)

After a conductor turn, the user opens Why?/trace and sees: the short plan or Haiku hint, each specialist that ran, any confirmation `request_id`s, and whether Ze asked the user or stalled. Parallel independent turns still show compound subtasks, not a fake conductor plan.

**Why this priority**: Without this, 153 can ship as “companion ate the turn” with no inspectability.

**Independent Test**: Fixture `MessageTrace` with ledger + confirmation ids renders in the trace panel. REST `/api/v0/messages/{id}/trace` and `trace_update` frames include the same fields. Codegen updated.

**Acceptance Scenarios**:

1. **Given** a conductor turn with two specialists and one confirmation, **When** the user opens trace, **Then** they see plan/hint, both specialists, and that confirmation’s `request_id`.
2. **Given** an ask-user / skipped step on the ledger, **When** trace renders, **Then** that status is visible (not only `done` tools).
3. **Given** an independent parallel turn, **When** trace renders, **Then** it does not present a companion conductor plan as if 153 rewrote it.

---

### User Story 2 - Progress text follows the sequence (Priority: P1)

While companion delegates, the typing/progress line changes with the specialist: checking calendar, then drafting mail — not a single mute wait. Keys live in companion (or conductor) locales, not hardcoded English in the engine.

**Why this priority**: The user-visible wait is the collaboration, not just the final bubble.

**Independent Test**: Progress reporter emits `conductor.checking_calendar` then `conductor.drafting_mail` (or equivalent pinned keys) when those delegates start.

**Acceptance Scenarios**:

1. **Given** companion starts a calendar delegate, **When** progress fires, **Then** the calendar checking key is used.
2. **Given** companion then starts a messenger draft/send delegate, **When** progress fires, **Then** the mail drafting key is used.
3. **Given** a speech-act one-shot reminder delegate, **When** progress fires, **Then** existing reminder progress MAY be used; conductor keys are not required to replace them.

---

### User Story 3 - Eval proves the four claims (Priority: P1)

Eval scenarios (not product anecdotes) cover:

1. Sequential dependent: calendar then email; event id appears in the second fat brief; primary agent companion.
2. Independent parallel: does not go through companion as primary.
3. Speech-act one-shot still 146-honest (nested `tool_calls`, no dual forget).
4. Mid-sequence confirmation: after approve, the next specialist still runs.

**Why this priority**: Roadmap: 154 is how we know 153 is true.

**Independent Test**: YAML in `eval/scenarios/` with those ids; judges/criteria match. Unit tests may stand in where full graph eval is too heavy, but the four scenarios MUST exist as eval entries.

**Acceptance Scenarios**:

1. **Given** `conductor_sequential_calendar_email`, **When** eval runs, **Then** expected primary is companion; calendar tool then messenger tool; second `delegate_to_agent` arguments include the event identifier from the first result (`prior_outputs` or `inputs`).
2. **Given** `routing_independent_parallel_not_companion`, **When** eval/routing asserts, **Then** primary is not companion (compound synthesize path).
3. **Given** `conductor_speech_act_146_honest`, **When** “forget the dentist” cancel runs, **Then** nested cancel tool succeeds and `forget_fact` is not dual-written.
4. **Given** `conductor_mid_sequence_confirmation`, **When** a Mode.CONFIRM specialist invocation (for example calendar `create`, not messenger `create` which may be DRAFT_ONLY) is approved, **Then** a later specialist in the ledger is `done` or running, not dropped.

---

## Edge Cases

- Trace payload missing ledger (old messages): panel omits the conductor section; no crash.
- Codegen: regenerate from OpenAPI; do not hand-edit only TS.
- Eval `expected_agent: email` vs `messenger`: use the live agent name (`messenger` if that is the registry name).
- Do not reintroduce `plan_sequential` to make eval green.
- Progress keys unused on specialist-primary calendar reads: calendar’s own keys remain.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose conductor plan/hint, per-specialist ledger, confirmation `request_id`s, and ask/stall status on `MessageTrace`, REST trace, and `trace_update` frames. The trace panel MUST render them.
- **FR-002**: System MUST emit progress keys `conductor.checking_calendar` and `conductor.drafting_mail` when companion starts those delegates (locale strings user-visible).
- **FR-003**: Eval MUST include `conductor_sequential_calendar_email` with event id in the later brief.
- **FR-004**: Eval MUST include `routing_independent_parallel_not_companion` asserting companion is not primary.
- **FR-005**: Eval MUST include `conductor_speech_act_146_honest` for nested-delegate honesty.
- **FR-006**: Eval MUST include `conductor_mid_sequence_confirmation` proving resume continues the sequence.
- **FR-007**: This phase MUST NOT delete 151 ACI fields, MUST NOT restore `plan_sequential`, MUST NOT implement promote-to-workflow/goal, MUST NOT change graph parallel to per-subtask gates.

### Key Entities

- **Conductor trace section**: UI + API view of 153 ledger.
- **Progress keys**: Locale keys for sequence-visible waiting.
- **Eval scenario**: YAML id + expected routing/tools/honesty.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of fixture conductor traces show plan, specialists, and confirmation ids in the panel without a blank crash.
- **SC-002**: 100% of tested calendar-then-mail conductor runs emit both pinned progress keys in order.
- **SC-003**: All four eval scenario ids exist and their documented criteria can fail a run that violates the matching FR.
- **SC-004**: Independent parallel fixtures still fail if primary is companion.

---

## Assumptions

- 153 Implemented before this product code; ledger fields already on `MessageTrace`.
- Agent registry name for mail is `messenger` (update eval if still labeled `email`).
- Speech-act eval can reuse 146 fixtures with conductor tags.

## Out of Scope

- Promote to workflow/goal.
- Magentic stall outer loop as a new product control.
- Parallel graph per-subtask capability.
- Changing 151/152 contracts except adding trace serialization.

## Verbatim Constraints

- `conductor.checking_calendar`
- `conductor.drafting_mail`
- `conductor_sequential_calendar_email`
- `routing_independent_parallel_not_companion`
- `conductor_speech_act_146_honest`
- `conductor_mid_sequence_confirmation`
- `request_id`
- `MessageTrace`
- `trace_update`
- `prior_outputs`
- `inputs`
- Principle VIII

## After this feature / Future work

Roadmap “After 154”: stall/replan, promote to workflow/goal, parallel per-subtask gates.
