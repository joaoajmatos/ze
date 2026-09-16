# Tasks: Parallel Per-Subtask Gates

**Input**: Design documents from `/specs/phases/158-parallel-subtask-gates/`

**Tests**: Required. Fail-first. Do not implement 153 sequential execute.

---

## Phase 1: Setup

- [x] **T001** Confirm 155 rewrite still sends mixed gather+act to companion; this work only touches remaining `is_compound` fan-out · `core/engine/ze-core/ze_core/orchestration/nodes/routing.py`

---

## Phase 2: Foundational

- [x] **T002** Fail-first: replace `test_compound_mixed_read_write_still_strictest_wins` so an EXECUTE sibling is not held by a sibling AWAIT · `core/engine/ze-core/tests/orchestration/nodes/test_execution.py`
- [x] **T003** Fail-first: all-EXECUTE independent multi-read still gathers; all-BLOCKED still blocks · `core/engine/ze-core/tests/orchestration/nodes/test_execution.py`

**Checkpoint**: Old strictest-wins assertion is gone from the intended successor tests (red).

---

## Phase 3: User Story 1 — Split gates (P1) 🎯 MVP

**Goal**: Allowed job runs; neighbor waits on its own `request_id`.

- [x] **T004** [US1] `capability_check` writes `subtask_gate_decisions`; compound MUST NOT `min()` to a single AWAIT that holds EXECUTE siblings · `core/engine/ze-core/ze_core/orchestration/nodes/execution.py`
- [x] **T005** [US1] Edges: mixed compound goes to `execute_tool`, not envelope-wide `draft_response` · `core/engine/ze-core/ze_core/orchestration/edges.py`
- [x] **T006** [US1] `_execute_compound` runs EXECUTE subtasks now; AWAIT subtasks do not `run`; persist confirmation per `request_id` · `core/engine/ze-core/ze_core/orchestration/nodes/execution.py`
- [x] **T007** [US1] Resume: approve runs only that subtask; deny skips that write; 113 isolation · tests + execution/confirmation path

**Checkpoint**: US1 testable.

---

## Phase 4: User Story 2 — Fan-out + partial synthesize (P1)

- [x] **T008** [US2] Two EXECUTE reads still `asyncio.gather` + synthesize · `test_execution.py`
- [x] **T009** [US2] Synthesize / final reply uses only completed `subtask_results`; blocked/denied not claimed successful · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` and/or execute_tool
- [x] **T010** [US2] Two act-only AWAIT: neither write runs until its own confirm · `test_execution.py`

**Checkpoint**: US2 testable.

---

## Phase 5: User Story 3 — DRAFT/BLOCKED per specialist (P2)

- [x] **T011** [US3] EXECUTE + DRAFT: A executes, B drafts only · `test_execution.py`
- [x] **T012** [US3] Budget overage composes per subtask like 152, not one AWAIT appended then `min()` · `test_execution.py`

**Checkpoint**: US3 testable.

---

## Phase 6: Polish

- [x] **T013** [P] Conductor/`run_delegate` tests still pass; grep no `plan_sequential` restore · `core/engine/ze-core/tests/`
- [x] **T014** [P] Eval optional id for parallel mixed-decision; 154/155 ids untouched · `eval/scenarios/`
- [x] **T015** Roadmap/README: 158 Ready to implement; ruff; `make test-core` orchestration nodes

---

## Dependencies & Execution Order

T001 → T002–T003 → T004–T007 (T004 before T005/T006). T008–T010 after partition exists. T011–T012 after T006. T013–T015 last.

T004 and T006 share `execution.py` — sequential.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T004, T005 |
| FR-002 | T002, T006 |
| FR-003 | T006, T007, T010 |
| FR-004 | T011, T012 |
| FR-005 | T009 |
| FR-006 | T001, T013 |
| FR-007 | T003 |
