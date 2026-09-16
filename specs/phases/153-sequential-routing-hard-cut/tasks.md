# Tasks: Sequential Routing Hard-Cut

**Input**: Design documents from `/specs/phases/153-sequential-routing-hard-cut/`

**Tests**: Required. Fail-first. Product code only after 151 and 152 are Implemented.

---

## Phase 1: Setup

- [ ] **T001** Grep `plan_sequential`, `dynamic_plan_steps`, `after_decompose`, sequential `_execute_compound` · repo

---

## Phase 2: Foundational

**Wave 2 — fail-first routing tests (same package, sequential if same file):**

- [ ] **T002** Fail-first: sequential multi-subtask → companion primary; `after_decompose` is not `plan_sequential` · `core/engine/ze-core/tests/orchestration/test_edges.py`
- [ ] **T003** [P] Fail-first: independent compound still fan-out path · `core/engine/ze-core/tests/orchestration/nodes/test_execution.py`
- [ ] **T004** [P] Fail-first: `plan_sequential` / `dynamic_plan_steps` absent from graph compile / state · `core/engine/ze-core/tests/`

**Checkpoint**: Tests describe the hard-cut.

---

## Phase 3: User Story 1 — Conductor routing + delete planner (P1) 🎯 MVP

**Goal**: Dependent multi-specialist turns execute companion. Planner path is gone.

**Wave 3:**

- [ ] **T005** [US1] Envelope rewrite: sequential + len(subtasks)>1 → companion; stash `conductor_hint` · `core/engine/ze-core/ze_core/orchestration/nodes/routing.py` and/or `edges.py`
- [ ] **T006** [US1] Remove `plan_sequential` node, function, exports, END edge · `graph.py`, `routing.py`, `nodes/__init__.py`
- [ ] **T007** [US1] Delete `dynamic_plan_steps` / `dynamic_plan_high_risk` from `AgentState` and `turn.py`
- [ ] **T008** [US1] Delete `_execute_compound` sequential execute loop · `execution.py`

**Checkpoint**: US1 graph tests green. No second sequence owner.

---

## Phase 4: User Story 2 — Parallel and single-domain unchanged (P1)

**Goal**: Independent multi-read still synthesizes. Single-domain stays specialist. Sequential+one subtask stays specialist.

- [ ] **T009** [US2] Preserve parallel gather + synthesize; tests for single-domain and one-subtask sequential · routing + execution tests
- [ ] **T010** [US2] Confirm research still has no `delegate_to_agent` · research agent

**Checkpoint**: US2 independently testable.

---

## Phase 5: User Story 3 — Description, instructions, ledger (P2)

**Goal**: Embeddings match conductor job. Ledger on MessageTrace. No auto workflow.

- [ ] **T011** [US3] Rewrite companion `description` + conductor inner-loop instructions (scale effort; hint is disposable) · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [ ] **T012** [US3] Turn-local `conductor_ledger` on state; copy onto `MessageTrace` · state + `messages/types.py` + `record_trace`
- [ ] **T013** [US3] Tests: description mentions coordination; ledger present; no workflow insert · tests

**Checkpoint**: 154 can render fields that now exist.

---

## Phase 6: Polish

- [ ] **T014** Update `docs/` or core routing spec only if they still document planner→END (honesty; no dual path)
- [ ] **T015** Grep: zero conversation-graph `plan_sequential`; companion has no calendar imports; no 154 panel files; `run_delegate` still uses 152 evaluate (no parent `gate_decision` copy)
- [ ] **T016** Validate: `make test-core` and `make test-personal` (or equivalent) + ruff

---

## Dependencies & Execution Order

T001 → T002–T004 → T005–T008 → T009–T010 → T011–T013 → T014–T016.

Do not start 154 product tasks in this tree.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T002, T005 |
| FR-002 | T003, T009 |
| FR-003 | T004, T006, T007, T008, T015 |
| FR-004 | T005 |
| FR-005 | T011 |
| FR-006 | T012, T013 |
| FR-007 | T010, T015 |
| FR-008 | T015 |
