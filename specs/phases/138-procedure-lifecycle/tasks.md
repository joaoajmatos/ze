---
description: "Task list for Governed Procedure Lifecycle (Phase 138)"
---

# Tasks: Governed Procedure Lifecycle

**Input**: Design documents from `/specs/phases/138-procedure-lifecycle/`

**Prerequisites**: Phase 137 evidence/learning vocabulary; plan.md, spec.md, research.md,
data-model.md, contracts/procedure-admission.md, quickstart.md.

**Tests**: Included — constitution Principle V. Use mocked asyncpg/LLM; no real workspace or
external skill execution.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent in its wave and different file(s)
- **[US#]**: User story from spec.md

---

## Phase 1: Setup and hard-cut inventory

- [ ] T001 Inventory every production `propose_procedure` caller and every direct
  `INSERT INTO memory_procedures`, including goal executor, workflow graph, and dream promoter;
  identify the newest `zm` migration slot · repository scan
- [ ] T002 Verify Phase 137's exported `Evidence`/`Learning` types, source-reference validation,
  and retention semantics; record exact imports in implementation notes without duplicating them ·
  `core/**/` Phase 137 package and `packages/ze-sdk/`
- [ ] T003 Add a lifecycle migration skeleton with legacy-row hard-cut decision documented
  (normalize into explicit legacy reviewed state or retire); do not implement dual-read/write ·
  `core/cognition/ze-memory/ze_memory/migrations/versions/zm0xx_procedure_lifecycle.py`

## Phase 2: Foundational lifecycle boundary

**Purpose**: Establish types, store invariants, one admission path, and the public API hard cut
before converting sources.

- [ ] T004 Define ProcedureIdentity, ProcedureCandidate, ProcedureAdmission, ProcedureVersion,
  ProcedureFeedback, lifecycle statuses/events, and provisional-resolution types that reference
  Phase 137 evidence/learning values ·
  `core/cognition/ze-memory/ze_memory/procedures/types.py`
- [ ] T005 Define typed lifecycle errors for incomplete candidates, invalid evidence, unapproved
  workspace runs, invalid transitions, missing action records, and unavailable rollback targets ·
  `core/cognition/ze-memory/ze_memory/procedures/errors.py`
- [ ] T006 Define private store protocol and transactional persistence for candidates, immutable
  versions, decisions, feedback, and lifecycle events; enforce one active version per identity ·
  `core/cognition/ze-memory/ze_memory/procedures/store.py`
- [ ] T007 Implement the sole `submit_procedure_candidate`, review/admit, feedback, rollback, and
  active-only retrieval service from the contract ·
  `core/cognition/ze-memory/ze_memory/procedures/admission.py`
- [ ] T008 [P] Add unit tests for type validation and Phase 137 evidence/learning reference
  preservation · `core/cognition/ze-memory/tests/procedures/test_types.py`
- [ ] T009 [P] Add store tests for immutable lineage, one-active-version invariant, and
  append-only feedback · `core/cognition/ze-memory/tests/procedures/test_store.py`
- [ ] T010 [P] Add admission tests for approve/reject/needs-review and rejection before
  persistence · `core/cognition/ze-memory/tests/procedures/test_admission.py`
- [ ] T011 Remove `propose_procedure` from `MemoryStore` and all SDK public re-exports; expose
  only the governed admission contract required by source packages ·
  `core/cognition/ze-memory/ze_memory/store.py` and `packages/ze-sdk/ze_sdk/memory.py`

**Checkpoint**: A candidate can be admitted as exactly one active version, but no legacy source
can directly persist a procedure.

## Phase 3: User Story 1 — Grounded source candidates (Priority: P1) 🎯 MVP

**Goal**: Every supported source submits its evidence-backed candidate through the one door.

**Independent Test**: Source tests assert candidate submission and zero direct persistence.

- [ ] T012 [P] [US1] Add goal-completion extraction tests asserting candidate evidence/learning
  refs and no direct writer · `core/automation/ze-automation/tests/goal_engine/test_executor.py`
- [ ] T013 [P] [US1] Add workflow-completion extraction tests asserting candidate submission and
  no direct writer · `plugins/ze-personal/tests/graph/test_workflow.py`
- [ ] T014 [P] [US1] Add approved/unapproved workspace-run adapter tests ·
  `core/ops/ze-workspace/tests/test_procedure_candidates.py`
- [ ] T015 [P] [US1] Add repeated-action-pattern candidate tests proving failure evidence is not
  silently promoted · `core/cognition/ze-memory/tests/procedures/test_patterns.py`
- [ ] T016 [P] [US1] Add explicit-instruction and imported-skill candidate tests, including no
  `allowed-tools` or execution behavior change ·
  `core/automation/ze-skills/tests/test_procedure_candidates.py`
- [ ] T017 [P] [US1] Add reviewed dream/reflection candidate tests with reviewer evidence ·
  `core/cognition/ze-memory/tests/dream/test_procedure_promotion.py`
- [ ] T018 [US1] Convert completed-goal extraction to construct and submit a candidate; replace
  process-local write behavior only, not goal planning ·
  `core/automation/ze-automation/ze_automation/goals/executor.py`
- [ ] T019 [US1] Convert completed-workflow extraction to submit a candidate ·
  `plugins/ze-personal/ze_personal/graph/workflow.py`
- [ ] T020 [US1] Implement approved workspace-run, repeated-pattern, explicit-instruction, and
  imported-skill source adapters using the common contract ·
  `core/ops/ze-workspace/`, `core/cognition/ze-memory/ze_memory/procedures/`, and
  `core/automation/ze-skills/`
- [ ] T021 [US1] Replace dream promoter procedure INSERT with reviewed-artifact candidate
  submission; retain the existing dream review gate ·
  `core/cognition/ze-memory/ze_memory/dream/promoter.py`

**Checkpoint**: All seven source classes produce candidates through one path.

## Phase 4: User Story 2 — Admission review (Priority: P1)

- [ ] T022 [P] [US2] Add tests for operational completeness, source-specific eligibility, and
  durable reasons for reject/needs-review ·
  `core/cognition/ze-memory/tests/procedures/test_admission.py`
- [ ] T023 [P] [US2] Add retrieval tests that exclude pending/rejected/superseded versions by
  default and include history only for review ·
  `core/cognition/ze-memory/tests/procedures/test_retrieval.py`
- [ ] T024 [US2] Implement completeness and canonical-identity matching rules in admission,
  without generic arbitration · `core/cognition/ze-memory/ze_memory/procedures/admission.py`
- [ ] T025 [US2] Wire existing review/audit route or component to show candidate decision,
  provenance, and Phase 137 evidence/learning references; add only the minimal lifecycle review
  surface · `apps/ze-api/ze_api/api/routes/` and `apps/ze-web/src/`

## Phase 5: User Story 3 — Versioning and rollback (Priority: P1)

- [ ] T026 [P] [US3] Add transactional tests for v1 admission, v2 supersession, audit lineage,
  rollback-to-prior, and retire-without-target ·
  `core/cognition/ze-memory/tests/procedures/test_versioning.py`
- [ ] T027 [US3] Implement material-revision admission, immutable version creation,
  supersession, rollback eligibility, restoration, and retirement ·
  `core/cognition/ze-memory/ze_memory/procedures/admission.py`
- [ ] T028 [US3] Add lifecycle-history projection for versions, decisions, and reasons ·
  `core/cognition/ze-memory/ze_memory/procedures/retrieval.py`

## Phase 6: User Story 4 — Use feedback (Priority: P2)

- [ ] T029 [P] [US4] Add feedback tests for ActionRecord linkage, append-only outcomes,
  failure-triggered review, and no automatic mutation ·
  `core/cognition/ze-memory/tests/procedures/test_feedback.py`
- [ ] T030 [US4] Implement feedback recording and review indication using existing execution
  records; do not create generic action-result production ·
  `core/cognition/ze-memory/ze_memory/procedures/admission.py`

## Phase 7: User Story 5 — Provisional resolution (Priority: P2)

- [ ] T031 [P] [US5] Add executor tests for completion submission, abandonment/cancellation
  discard, and restart recovery ·
  `core/automation/ze-automation/tests/goal_engine/test_executor.py`
- [ ] T032 [US5] Replace `_provisional_procedures` process-local retention with durable
  candidate handoff or explicit discard events for every terminal path ·
  `core/automation/ze-automation/ze_automation/goals/executor.py`

## Phase 8: Polish and verification

- [ ] T033 [P] Migrate legacy procedure rows according to T003's documented hard-cut decision;
  add migration tests with no dual-read/write path ·
  `core/cognition/ze-memory/ze_memory/migrations/versions/zm0xx_procedure_lifecycle.py`
- [ ] T034 [P] Scan production code for prohibited public writer/direct INSERT paths and ensure
  skills, workspace gates, generic arbitration, and generic ActionRecord production were not
  changed · repository scan
- [ ] T035 Run the quickstart suites: `make test-memory`, `make test-automation`,
  `make test-workspace`, `make test-skills`, affected API/web tests, and `make lint` · repo root

## Dependencies and execution order

- T001–T003 establish source and migration facts.
- T004–T011 block all user stories.
- US1 source adapters can run in parallel after T007/T011, then converge at T018–T021.
- US2 and US3 follow the foundation; US3 depends on canonical admission from US2.
- US4 depends on versions; US5 depends on submission contract.
- Polish follows all stories.

## MVP

T001–T011, then T012/T013/T017/T018/T019/T021 deliver a governed source path for the three
existing direct writers. Remaining sources, review UI, feedback, and provisional recovery extend
that boundary without reopening it.
