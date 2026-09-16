# Tasks: Action Instrumentation

**Input**: Design documents from `/specs/phases/136-action-instrumentation/`  
**Prerequisites**: Phase 135 ActionRecord ledger is available  
**Tests**: Required for every producer family; mock all I/O  
**Organization**: User Story 1 (workspace/messenger), User Story 2 (calendar/reminders), User Story 3 (automation/outreach).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after its stated dependency
- **[Story]**: US1, US2, or US3

## Phase 1: Validate ledger contract

**Purpose**: Confirm Phase 135 has the required source, outcome, context, and idempotency semantics before changing producers.

- [x] T001 Confirm Phase 135’s `ActionRecord` contract supports source references, context IDs,
  immutable idempotent append, and causal non-terminal-to-terminal observations; record a Phase
  135 vocabulary gap as a blocker rather than extending the ledger contract locally
  ([contracts/action-instrumentation.md](./contracts/action-instrumentation.md)).
- [x] T002 Confirm ledger ownership/migration is Phase 135’s and identify its injected recorder API; do not create another action table or direct producer SQL writer (FR-002, FR-008).
- [x] T003 Add or update Phase 135 contract tests for exact-one immutable append and causally
  linked non-terminal-to-terminal observations; do not reinterpret the ledger's append-only
  semantics (FR-003, FR-006).

## Phase 2: Shared producer boundary

**Purpose**: Make outcome/context available at the producer edges.

- [x] T004 Define the narrow injected recorder dependency and typed source/context adapters at composition boundaries. Preserve package layering: no cross-plugin store imports (FR-007, FR-008).
- [x] T005 [P] Establish a shared test fixture/helper for asserting stable idempotency key, source citation, no premature terminal write, and context propagation (FR-010).
- [x] T006 Add recorder-failure observability/retry posture at the integration boundary: domain effect remains authoritative; replay uses the same source/key and never repeats a side effect (FR-009).

**Checkpoint**: The recorder can be injected without a producer direct SQL path or a compatibility callback.

## Phase 3: User Story 1 — Workspace and messenger (Priority: P1)

**Goal**: Terminal workspace runs and outbound sends create accurate, exactly-once action records.

### Tests

- [x] T007 [P] [US1] Add workspace tests for success, failure, cancelled if supported, replay/idempotency, source `workspace_run`, and available session/message/workspace context.
- [x] T008 [P] [US1] Add messenger outbound tests for success, failure, durable pending dispatch where supported, causally linked terminal resolution, replay/idempotency, source citation, and channel/thread/turn context.

### Implementation

- [x] T009 [US1] Instrument workspace run terminalization after source-run persistence with the Phase 135 recorder; derive source identity from the workspace run (FR-001, FR-004, FR-007).
- [x] T010 [US1] Instrument outbound messenger send result handling after durable attempt/provider outcome; never mark success at request construction (FR-001, FR-004, FR-005).

**Checkpoint**: US1 tests show one source-cited record per run/send regardless of callback replay.

## Phase 4: User Story 2 — Calendar and reminders (Priority: P1)

**Goal**: Calendar/reminder mutations preserve outcome distinctions and durable citations.

### Tests

- [x] T011 [P] [US2] Add calendar mutation tests covering successful create/update/delete, provider failure, cancellation/pending where reachable, partial multi-effect behavior, source reference, and turn context.
- [x] T012 [P] [US2] Add reminder mutation tests covering create/update/delete/schedule outcomes, idempotent replay, reminder source citation, and available turn context.

### Implementation

- [x] T013 [US2] Instrument calendar mutation terminal points with source-derived action identities and factual outcome mapping (FR-001, FR-003, FR-005).
- [x] T014 [US2] Instrument reminder mutation terminal points; use `partial` only for one identifiable mixed-result operation, otherwise emit independently identifiable actions (FR-001, FR-005).

**Checkpoint**: Calendar/reminder state stays canonical in its domain stores and records never reduce cancellation to failure.

## Phase 5: User Story 3 — Automation and prospecting (Priority: P1)

**Goal**: Goal/workflow traces and prospecting outreach are ledger-cited without lifecycle ownership moving.

### Tests

- [x] T015 [P] [US3] Add goal execution tests for success, failure, cancellation/retry as applicable, trace citation, and goal/milestone/session/message context.
- [x] T016 [P] [US3] Add workflow execution tests for success, cancellation, replay/idempotency, workflow/run/trace citations, and available context.
- [x] T017 [P] [US3] Add prospecting outreach tests for success, failure/pending as applicable, retry replay, source `prospect_outreach`, and channel/outreach context.

### Implementation

- [x] T018 [US3] Instrument goal execution after its durable execution trace records the outcome; ActionRecord must not become the goal recovery state (FR-001, FR-002).
- [x] T019 [US3] Instrument workflow execution terminalization after the workflow domain commits its run/trace outcome (FR-001, FR-002).
- [x] T020 [US3] Instrument prospecting outreach outcome handling after the outreach record is durable; retries reuse the outreach-derived identity (FR-001, FR-003).

**Checkpoint**: Every automation/outreach record cites a domain trace/outreach source and does not alter existing lifecycle transitions.

## Phase 6: Cross-cutting verification

- [x] T021 [P] Exercise every `pending → terminal` producer path and verify causally linked immutable observations preserve initiation and final observation chronology (FR-004, FR-006).
- [x] T022 [P] Replay each producer completion/resume path and assert exact-one ActionRecord by source-derived idempotency identity (SC-002).
- [x] T023 Verify source/correlation fields in all tests: record only available IDs, omit unknown values, and never fabricate a source reference (FR-007).
- [x] T024 Review all producer diffs for pre-v1 hard-cut compliance: remove replaced callbacks/contracts; add no shims or dual operational histories (FR-011).
- [x] T025 Run relevant package test targets, Phase 135 ledger tests, and `make lint` (SC-001–SC-005).
- [x] T026 Confirm excluded files/behaviors remain untouched: inbound perception, `signal_sources()`, learning/procedures, and arbitration/priority (FR-012).

## Dependencies & Execution Order

- T001–T003 precede all producer work.
- T004 and T006 precede implementations T009, T010, T013, T014, T018–T020.
- Within each story, tests may start after T004 and should fail before its implementation.
- US1, US2, and US3 implementation groups may proceed in parallel after Phase 2 if each touches separate packages.
- Phase 6 follows all producer implementations.

## Parallel Example

```text
Task: "Add workspace action-record tests"
Task: "Add calendar mutation action-record tests"
Task: "Add goal execution action-record tests"
```

## Implementation Strategy

**MVP**: T001–T006, then T007–T010. This proves the ledger boundary, chronology, and replay safety on the two clearest producer families.

**Incremental delivery**: Add calendar/reminders next, then automation/prospecting. Do not ship any producer family that records intent as success or uses the ledger as its recovery store.

**No commit**: Implementation should not create a git commit unless explicitly requested.
