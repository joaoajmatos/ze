---
description: "Task list for Governed Procedure Activation (Phase 139)"
---

# Tasks: Governed Procedure Activation

**Input**: Design documents from `/specs/phases/139-procedure-activation/`

**Prerequisites**: Phase 138 lifecycle contract; plan.md; spec.md; research.md; data-model.md; contracts/procedure-activation.md; quickstart.md

**Tests**: Included — Constitution Principle V.

**Organization**: Lifecycle-aware discovery foundation → safe invocation/trace (US1–US3) → management surface (US4) → production caller hard cut and validation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent within its wave (different files, no incomplete dependency)
- **[US#]**: User story from spec.md

## Path Conventions

See plan.md Project Structure. Substitute the concrete Phase-138 procedure owner path only if it differs from `core/cognition/ze-memory/ze_memory/procedures/`; do not create a second lifecycle owner.

---

## Phase 1: Setup

**Purpose**: Reconcile Phase 139 with the delivered Phase-138 public lifecycle contract before writing activation code.

- [x] T001 Read Phase-138 procedure lifecycle specification and implementation; record the concrete eligible-version, revision, evidence, confidence, edit, disable, and review intake APIs in `specs/phases/139-procedure-activation/research.md`
- [x] T002 Audit registered agents/planners for task-context and existing direct procedure retrieval callers; enumerate integrations and tests in `specs/phases/139-procedure-activation/plan.md`
- [x] T003 [P] Confirm generated-client workflow and applicable API/web test targets in `docs/testing.md` and `packages/ze-client/`; append exact commands to `specs/phases/139-procedure-activation/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish typed lifecycle-aware discovery, invocation, feedback, and persistence contracts. Blocks all user stories.

**⚠️ CRITICAL**: Do not start caller integrations or management UI before this phase.

**Wave 1 — independent:**

- [x] T004 [P] Add failing unit tests for eligibility filtering, trigger/precondition match states, and monotonic tool intersection in `core/cognition/ze-memory/tests/procedures/test_discovery.py`
- [x] T005 [P] Add failing unit tests for immutable invocation/action links, idempotent terminal feedback, and no direct confidence mutation in `core/cognition/ze-memory/tests/procedures/test_activation.py`
- [x] T006 [P] Extend Phase-138 procedure domain dataclasses/protocols with `ProcedureTaskContext`, `ProcedureMatch`, `ProcedureInvocation`, `ProcedureActionLink`, and `ProcedureOutcomeFeedback` in `core/cognition/ze-memory/ze_memory/procedures/types.py`

**Then:**

- [x] T007 Implement lifecycle-aware `ProcedureDiscovery.match`: filter Phase-138 eligibility first, evaluate trigger/preconditions deterministically, and return ready/blocked/not-relevant matches with rationale in `core/cognition/ze-memory/ze_memory/procedures/discovery.py`
- [x] T008 Implement explicit `ProcedureActivator` invocation, action-link recording, and idempotent outcome feedback forwarding to the Phase-138 review/confidence intake in `core/cognition/ze-memory/ze_memory/procedures/activation.py`
- [x] T009 Add a raw-SQL migration for invocation/outcome records only if Phase 138 does not provide an equivalent durable activation ledger in `core/cognition/ze-memory/ze_memory/migrations/versions/zmXXX_procedure_activation.py`
- [x] T010 Implement the owner-package store methods and typed errors required by discovery/activation in `core/cognition/ze-memory/ze_memory/procedures/store.py` and `core/cognition/ze-memory/ze_memory/store.py`
- [x] T011 Re-export only the stable discovery/activation contracts through `packages/ze-sdk/ze_sdk/memory.py` or `packages/ze-sdk/ze_sdk/procedures.py`

**Checkpoint**: A validated procedure can be matched, explicitly invoked, action-linked, and completed in unit tests without an agent, planner, route, or UI.

---

## Phase 3: User Story 1 - Discover validated procedures for a task (Priority: P1) 🎯 MVP

**Goal**: Every context-bearing agent/planner gets consistent advisory matches; unreviewed/disabled procedures cannot become actionable.

**Independent Test**: Seed each lifecycle state and assert the common consumer gets only ready or clearly blocked eligible guidance.

### Tests

- [x] T012 [P] [US1] Add goal planner integration tests for common discovery, ready/blocked prompt context, and removal of direct procedure retrieval in `core/automation/ze-automation/tests/goal_engine/test_planner.py`
- [x] T013 [P] [US1] Add workflow planner/graph integration tests for common discovery and advisory formatting in `core/automation/ze-automation/tests/workflow_engine/test_workflow_planner.py`
- [x] T014 [P] [US1] Add registry-driven tests covering each relevant agent integration identified by T002 in `core/engine/ze-core/tests/orchestration/test_procedure_discovery.py`

### Implementation

- [x] T015 [US1] Replace goal planner `_fetch_procedures` direct retrieval with the common lifecycle-aware discovery contract in `core/automation/ze-automation/ze_automation/goals/planner.py`
- [x] T016 [US1] Integrate common procedure discovery into workflow planning/replanning in `core/automation/ze-automation/ze_automation/workflow/planner.py`
- [x] T017 [US1] Inject advisory procedure matches into relevant agent/planner task context through the existing orchestration context path in `core/engine/ze-core/ze_core/orchestration/nodes/fetch_context.py`
- [x] T018 [US1] Wire concrete discovery dependencies in the composition root without importing procedure internals from plugins in `apps/ze-api/ze_api/container.py`

**Checkpoint**: US1 is independently useful: matching guidance reaches every audited relevant consumer, while no ineligible version is actionable.

---

## Phase 4: User Story 2 - Invoke an applicable procedure explicitly and safely (Priority: P1)

**Goal**: Explicit procedure selection guides actions but never grants authority.

**Independent Test**: Mock an eligible selection and prove execution cannot start implicitly or use any tool outside the intersection.

### Tests

- [x] T019 [P] [US2] Add orchestration tests for explicit invocation requirement, stale/disabled recheck, and capability-denied guided action trace in `core/engine/ze-core/tests/orchestration/test_procedure_activation.py`
- [x] T020 [P] [US2] Add agent-loop tests proving procedure tool hints narrow, never expand, agent and capability tool access in `core/contracts/ze-agents/tests/test_procedure_tool_access.py`

### Implementation

- [x] T021 [US2] Add explicit procedure invocation selection to the agent/planner action context, using only the SDK activation contract, in `core/engine/ze-core/ze_core/orchestration/procedure_activation.py`
- [x] T022 [US2] Apply `agent_allowed ∩ capability_allowed ∩ procedure_relevant` before every guided tool proposal and preserve normal confirmation/denial flow in `core/engine/ze-core/ze_core/orchestration/nodes/capability.py`
- [x] T023 [US2] Attach ready-match advisory context and explicit selected invocation state to relevant agent/planner prompts without converting a match into execution in `core/engine/ze-core/ze_core/orchestration/state.py`

**Checkpoint**: US2 is independently testable: an explicit invocation narrows actions and all actions still pass the existing gate.

---

## Phase 5: User Story 3 - Trace procedure-guided actions and improve the procedure (Priority: P2)

**Goal**: Procedure version and per-step action outcome remain auditable and produce governed feedback.

**Independent Test**: Complete a multi-step invocation with mixed results and resolve its historical version/evidence after a later edit or disablement.

### Tests

- [x] T024 [P] [US3] Add message/action trace serialization tests for invocation id, immutable procedure version, step reference, capability decision, and outcome in `core/engine/ze-core/tests/orchestration/test_message_trace.py`
- [x] T025 [P] [US3] Add activation feedback integration tests for success/failure/cancel, idempotency, and Phase-138-only confidence/lifecycle mutation in `core/cognition/ze-memory/tests/procedures/test_activation_feedback.py`

### Implementation

- [x] T026 [US3] Extend existing action/message trace types and serializers with the optional procedure action link in `core/engine/ze-core/ze_core/orchestration/trace.py`
- [x] T027 [US3] Record a procedure action link after each guided action, including denied/not-executed outcomes, in `core/engine/ze-core/ze_core/orchestration/nodes/execute_tool.py`
- [x] T028 [US3] Complete the invocation once on terminal turn/planner outcome and forward idempotent feedback to Phase 138 in `core/engine/ze-core/ze_core/orchestration/nodes/write_memory.py`
- [x] T029 [US3] Extend trace API schemas and generated client inputs/outputs for optional procedure provenance in `apps/ze-api/ze_api/api/schemas.py` and `packages/ze-client/`

**Checkpoint**: US3 provides inspectable version-level provenance and feedback without allowing activation to change governance.

---

## Phase 6: User Story 4 - Manage and review procedure guidance (Priority: P2)

**Goal**: Users can inspect, edit through governance, and immediately disable procedures.

**Independent Test**: Exercise list/detail/version/evidence/edit/disable via API and UI fixtures; confirm disablement removes new ready matches but preserves history.

### Tests

- [x] T030 [P] [US4] Add API route tests for list, detail/version/evidence, governed edit, disable, response metadata, and auth in `apps/ze-api/tests/api/test_procedures.py`
- [x] T031 [P] [US4] Add entity query/mutation and management widget tests for status labels, evidence, revision result, and disable confirmation in `apps/ze-web/src/widgets/procedure-management/ProcedureManagement.test.tsx`

### Implementation

- [x] T032 [US4] Add procedure list/detail/version/evidence/edit/disable REST router using Phase-138 lifecycle operations and declared OpenAPI metadata in `apps/ze-api/ze_api/api/routes/procedures.py`
- [x] T033 [US4] Add Pydantic request/response schemas that distinguish lifecycle/readiness states and expose historical version traceability in `apps/ze-api/ze_api/api/schemas.py`
- [x] T034 [US4] Regenerate and validate typed REST client methods in `packages/ze-client/`
- [x] T035 [US4] Create FSD procedure entity query hooks and formatting helpers in `apps/ze-web/src/entities/procedure/`
- [x] T036 [US4] Create governed edit/disable feature mutations in `apps/ze-web/src/features/procedure-review/`
- [x] T037 [US4] Create procedure management widget/page showing current state, evidence, outcomes, versions, edit outcome, and disable control in `apps/ze-web/src/widgets/procedure-management/`
- [x] T038 [US4] Register the page through the existing core route/navigation pattern in `apps/ze-web/src/shared/config/nav-routes.ts` and `apps/ze-web/src/app/router/routes.ts`

**Checkpoint**: US4 is independently useful: the user can inspect and stop unsafe guidance without losing its historical evidence.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T039 [P] Scan production callers to prove retired direct procedure retrieval paths are gone and no fallback/compatibility path remains; record results in `specs/phases/139-procedure-activation/quickstart.md`
- [x] T040 [P] Verify no edits rewire `signal_sources()`, contribution collision handling, or contribution arbitration; record results in `specs/phases/139-procedure-activation/quickstart.md`
- [x] T041 [P] Add regression tests ensuring procedure-less turns/plans retain prior behavior in `core/engine/ze-core/tests/orchestration/test_procedure_discovery.py`
- [x] T042 Run all quickstart validation targets and migrate a fresh development database if T009 added a migration; update `specs/phases/139-procedure-activation/quickstart.md` with results
- [x] T043 Update `specs/phases/139-procedure-activation/spec.md` status only after all tasks and validation pass; do not modify `specs/README.md` unless separately authorized

## Dependencies & Execution Order

- T001–T003 reconcile the delivered Phase-138 interface.
- T004–T011 establish the shared contract and block US1–US4.
- US1 (T012–T018) is the MVP and precedes execution integration.
- US2 (T019–T023) depends on US1's common match context.
- US3 (T024–T029) depends on US2 invocation records.
- US4 (T030–T038) depends on foundation and can begin API/UI work after T010; it does not require engine execution work.
- T039–T043 finish last.

## Parallel Opportunities

- T004–T006 can start together.
- After T011, T012–T014 and T030–T031 can run in parallel.
- T019/T020 and T024/T025 can each run in parallel after their relevant foundation.
- T035/T036 can progress in parallel once T034 produces the client surface.

## Implementation Strategy

1. Deliver the Phase-138-aware discovery contract and goal planner migration (US1).
2. Add explicit, capability-gated invocation and tool narrowing (US2).
3. Add durable traceability and governed feedback (US3).
4. Deliver management visibility and controls (US4).
5. Remove direct legacy retrieval callers and validate excluded scope.
