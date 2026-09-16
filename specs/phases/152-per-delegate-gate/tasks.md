# Tasks: Per-Delegate Capability and Confirmation

**Input**: Design documents from `/specs/phases/152-per-delegate-gate/`

**Tests**: Required. Fail-first. Depends on 151 Implemented at product time (fat ACI + companion-only caller).

---

## Phase 1: Setup

**Wave 1:**

- [x] **T001** [P] Confirm 151 result shape `{response, tool_calls}` and companion-only caller still specified; do not reintroduce `task` · `specs/phases/151-fat-delegate-aci/spec.md`
- [x] **T002** [P] Confirm confirmation store PK is `request_id` · `core/engine/ze-core/ze_core/conversation/confirmations/store.py`

---

## Phase 2: Foundational

**⟶ Wave 2 — sequential tests on delegate test file:**

- [x] **T003** Fail-first: injected evaluator sets worker `gate_decision`; parent EXECUTE is not copied · `core/engine/ze-core/tests/orchestration/test_delegate.py`
- [x] **T004** Fail-first: EXECUTE lookup then AWAIT_CONFIRMATION write; lookup `run` happened, write `run` did not · `core/engine/ze-core/tests/orchestration/test_delegate.py`

**⟶ Wave 3 — protocol + wiring:**

- [x] **T005** Define engine-injected evaluate callback (no `ze_core` import in `ze_agents`) · `core/contracts/ze-agents/ze_agents/`
- [x] **T006** `execute_tool` / single-agent context supplies CapabilityGate + spend budget wrapper · `core/engine/ze-core/ze_core/orchestration/nodes/execution.py`

**Checkpoint**: Evaluation can be stubbed in unit tests.

---

## Phase 3: User Story 1 — Per-invocation gate (P1) 🎯 MVP

**Goal**: Each `run_delegate` uses specialist+intent+budget. Lookups are not held for later writes.

**Independent Test**: Two delegates, first EXECUTE, second DRAFT or AWAIT_CONFIRMATION; first completed.

**Wave 4:**

- [x] **T007** [US1] Apply evaluated decision in `run_delegate`; delete parent copy · `core/contracts/ze-agents/ze_agents/delegate.py`
- [x] **T008** [US1] Compose spend over-ceiling with AWAIT_CONFIRMATION like `capability_check` · engine wrapper + `run_delegate`
- [x] **T009** [P] [US1] Lock: graph parallel `capability_check` still strictest-wins · `core/engine/ze-core/tests/orchestration/nodes/` or existing capability tests

**Checkpoint**: US1 testable without UI.

---

## Phase 4: User Story 2 — Pause and resume (P1)

**Goal**: AWAIT_CONFIRMATION pauses conductor; `request_id` resume runs that specialist; siblings isolated.

**Independent Test**: Approve path `run` count 0 then 1; two request_ids.

**Wave 5:**

- [x] **T010** [US2] Fail-first: AWAIT_CONFIRMATION does not call specialist `run` until approve · `core/engine/ze-core/tests/orchestration/test_delegate.py`
- [x] **T011** [US2] Persist/pause using `request_id`; kind distinguishes delegate invocation · confirmations + interrupt wiring
- [x] **T012** [US2] Resume: approved invocation EXECUTE `run` once; deny does not write · tests + implementation
- [x] **T013** [P] [US2] Dual `request_id` on one thread: answering one does not clear the other · `core/engine/ze-core/tests/`

**Checkpoint**: US2 independently testable.

---

## Phase 5: User Story 3 — Optional intent (P2)

**Goal**: Optional `intent` on ACI; omitted uses CapabilityGate default; 151 fields remain.

**Wave 6:**

- [x] **T014** [US3] Schema + `run_delegate` read optional `intent` · `core/contracts/ze-agents/ze_agents/delegate.py`
- [x] **T015** [US3] Tests: `read` vs `create` different decisions; omitted intent still runs speech-act style · `core/engine/ze-core/tests/orchestration/test_delegate.py`

**Checkpoint**: Speech-act one-shots without `intent` still work.

---

## Phase 6: Polish

- [x] **T016** Grep: no parent `gate_decision=` copy in `run_delegate`; no `plan_sequential` deletes; companion `description` untouched; no `ze_core` import in `delegate.py`
- [x] **T017** Validate: `make test-core` (delegate + confirmation + capability) and ruff

---

## Dependencies & Execution Order

Setup → T003–T006 → US1 T007–T009 → US2 T010–T013 → US3 T014–T015 → Polish. Same-file `test_delegate.py` tasks stay sequential.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T003, T005, T006, T007, T008 |
| FR-002 | T004, T007 |
| FR-003 | T010, T011, T012 |
| FR-004 | T002, T013 |
| FR-005 | T014, T015 |
| FR-006 | T005, T016 |
| FR-007 | T001, T009, T016 |
