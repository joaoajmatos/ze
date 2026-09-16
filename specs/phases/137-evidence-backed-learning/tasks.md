---
description: "Task list for Evidence-Backed Goal Learning (Phase 137)"
---

# Tasks: Evidence-Backed Goal Learning

**Input**: Design documents from `/specs/phases/137-evidence-backed-learning/`  
**Prerequisites**: Phase 136 ActionRecord contract, plan.md, spec.md, research.md, data-model.md, contracts/learning-promotion.md, quickstart.md  
**Tests**: Included — constitution Principle V.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent within its wave (different file, no incomplete dependency)
- **[US#]**: User story from spec.md

## Phase 1: Prerequisite and legacy inventory

- [x] T001 Verify Phase 136 exposes stable ActionRecord ids, verification/outcome state, execution context or lineage, timestamps, and redaction-safe summary; record any contract gap as a blocker rather than adding a local substitute · Phase 136 contract + `ze_automation` integration boundary
- [x] T002 [P] Inventory every production and test read/write of `Goal.learnings`, `goals.learnings`, `GoalLearning`, `goal_learnings`, `append_learnings`, `add_learning`, and `list_learnings` · repository scan
- [x] T003 [P] Add failing characterization tests for legacy goal detail, completion extraction, gate redirect, retrospective, planning context, and seed/reset behavior · `core/automation/ze-automation/tests/goal_engine/`

**Checkpoint**: The Phase 136 dependency and complete legacy removal surface are explicit.

## Phase 2: Authoritative model foundation (blocking)

**Purpose**: Create shared types, typed errors, schema, store interface, and store behavior before changing callers.

### Tests

- [x] T004 [P] Add domain tests for claim lifecycle constraints, evidence-source exclusivity, confidence bounds, and immutable review/relationship drafts · `core/automation/ze-automation/tests/goal_engine/test_learning_types.py`
- [x] T005 [P] Add migration tests covering rows, blob-only entries, row/blob duplicates, unrepresentable data failure, and removal of legacy table/column · `core/automation/ze-automation/tests/migrations/`
- [x] T006 [P] Add store tests for atomic claim-plus-evidence insert, active/history reads, and indexed detail summaries · `core/automation/ze-automation/tests/goal_engine/test_learning_postgres.py`

### Implementation

- [x] T007 Add `GoalLearning` authoritative types, lifecycle/review/relationship/promotion enums and typed `ZeError` subclasses; remove `Goal.learnings` and legacy fragment type from the domain public model · `core/automation/ze-automation/ze_automation/goals/types.py`, `errors.py`
- [x] T008 Add one `zc` migration creating claim/evidence/review/relationship/promotion tables, migrating representable legacy history, then dropping `goals.learnings` and `goal_learnings` with no compatibility view · `core/automation/ze-automation/ze_automation/migrations/versions/`
- [x] T009 Replace legacy GoalStore methods with authoritative typed APIs and implement transactional PostgreSQL persistence/detail reads · `goals/store.py`, `goals/postgres.py`

**Checkpoint**: New learning claims can persist once with evidence; legacy APIs/schema no longer exist.

## Phase 3: Evidence gate and extraction (US1, US2)

### Tests

- [x] T010 [P] [US1] Test executor extraction creates an evidence-backed candidate from a Phase 136 verified ActionRecord and never writes the legacy blob/table · `tests/goal_engine/test_executor.py`
- [x] T011 [P] [US2] Test eligibility: one action, same lineage retries, and one milestone fail; two independent consistent contexts pass; unresolved contradiction blocks · `tests/goal_engine/test_learning.py`
- [x] T012 [P] [US2] Test FACT gate: generated outcome generalization remains INFERENCE; direct supporting/user-confirmed assertion is the only FACT route · `tests/goal_engine/test_learning.py`

### Implementation

- [x] T013 Implement one learning eligibility service that validates Phase 136 evidence, context diversity, consistency, and claim-kind permissions · `ze_automation/goals/learning.py`
- [x] T014 [US1] Replace executor `add_learning`/`append_learnings` calls in milestone completion and gate redirect with ActionRecord-linked candidate creation · `ze_automation/goals/executor.py`
- [x] T015 [US2] Update planner extraction prompts/parsers to emit bounded candidate wording and evidence references without presenting generalizations as FACT · `ze_automation/goals/planner.py`

**Checkpoint**: Automated learning is one evidence-backed INFERENCE with a deterministic eligibility result.

## Phase 4: Promotion, review, contradiction, and retraction (US2, US3)

### Tests

- [x] T016 [P] [US2] Test that active inferred learning is returned only by the labeled learning
  projection, while an explicitly user-confirmed FACT publication uses the perception-fact
  contribution path idempotently, retains citations, and records failure without a partial claim ·
  `tests/goal_engine/test_learning_promotion.py`
- [x] T017 [P] [US3] Test approve/reject/correct/defer transitions, append-only review history, user confirmation evidence, retraction, and supersession · `tests/goal_engine/test_learning_review.py`
- [x] T018 [P] [US3] Test material contradiction records links and enters review-needed without automatic winner/retraction · `tests/goal_engine/test_learning_contradiction.py`

### Implementation

- [x] T019 [US2] Implement labeled learning retrieval for active INFERENCE records and optional
  idempotent FACT publication only at the user-confirmation/direct-fact boundary through the
  licensed perception-fact path; do not create a fact-write bypass ·
  `ze_automation/goals/learning.py`, composition wiring
- [x] T020 [US3] Implement review, correction-to-new-claim, retraction, and supersession persistence/services · `ze_automation/goals/learning.py`, `goals/postgres.py`
- [x] T021 [US3] Integrate existing NLI/claim comparison to record contradiction evidence and queue review; do not call generic contribution arbitration · `ze_automation/goals/learning.py`

**Checkpoint**: Claims can be safely promoted or corrected without losing provenance.

## Phase 5: Consumers and API/UI (US4)

### Tests

- [x] T022 [P] [US4] Test planner/executor consume only active eligible learning and receive explicit FACT/INFERENCE labels; raw ActionRecord retrieval remains separate · `tests/goal_engine/test_planner.py`, `test_executor.py`
- [x] T023 [P] [US4] Test priority adapter excludes non-active claims and uses only bounded relevance-scored context without creating overrides/notifications · `core/arbitration/ze-priority/tests/` or existing consumer boundary tests
- [x] T024 [P] [US3] Add API tests for learning summaries, history/detail, review validation, promotion responses, and redaction-safe evidence · `apps/ze-api/tests/api/`
- [x] T025 [P] [US3] Add web tests for doctrine badges, evidence summary, review actions, lifecycle history, and retracted display · `apps/ze-web/src/**/**.test.tsx`

### Implementation

- [x] T026 [US4] Replace planner/executor legacy learning prompt reads with `list_eligible_learnings`; keep INFERENCE wording visibly tentative · `ze_automation/goals/planner.py`, `executor.py`
- [x] T027 [US4] Add the bounded learning read adapter for priority consumers; exclude pending/review-needed/retracted/superseded claims and leave priority override/push behavior untouched · `ze-priority` composition boundary
- [x] T028 [US3] Replace goal API schemas/routes with authoritative summaries, learning detail/history, review, and promotion endpoints; regenerate `@ze/client` · `apps/ze-api`, `packages/ze-client`
- [x] T029 [US3] Update goal detail and add focused learning review UI following FSD boundaries · `apps/ze-web/src/entities/goal`, `features/review-goal-learning`, `widgets/goal-detail`

## Phase 6: Hard-cut cleanup and verification

- [x] T030 [P] Remove/adapt seed and reset references to legacy table/blob; seed ActionRecords before learning evidence where required · `core/ops/ze-seed/`, `ze-onboarding/reset.py`
- [x] T031 [P] Search production code for zero `goals.learnings`, `goal_learnings`, `append_learnings`, `add_learning`, and legacy `list_learnings` references; update only direct compile breaks · repository scan
- [x] T032 Update API/OpenAPI snapshots and generated types following the intentional pre-v1 break · API/client generation workflow
- [x] T033 Run quickstart suites, migration tests, API/client generation verification, and `make lint`; confirm no edits to `signal_sources`, contribution arbitration, push budget, or priority override store · repository root

## Dependencies & Execution Order

- T001 blocks every implementation task.
- T004–T009 block all caller migration.
- T013 blocks T014–T021.
- T019–T021 block consumer/API/UI work that exposes lifecycle.
- T030–T033 are final hard-cut verification.
- Parallel tasks are explicitly marked `[P]`; do not parallelize same-file work.
