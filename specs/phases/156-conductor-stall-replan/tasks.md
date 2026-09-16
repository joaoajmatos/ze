# Tasks: Conductor Stall / Replan

**Input**: Design documents from `/specs/phases/156-conductor-stall-replan/`

**Tests**: Required. Product code after 155 Implemented.

---

## Phase 1: Setup

- [x] **T001** Confirm 155 mixed rewrite and 153 ledger statuses exist in code at implement time · `core/engine/ze-core/ze_core/orchestration/nodes/routing.py`

---

## Phase 2: Foundational

- [x] **T002** Fail-first: first stall allows one more `run_delegate`; third same-agent call does not run the specialist · `core/engine/ze-core/tests/orchestration/test_delegate.py`
- [x] **T003** Add turn counters on `AgentContext` / `AgentState` and copy them like `conductor_ledger` through execute/resume · `core/contracts/ze-agents/ze_agents/types.py` and `core/engine/ze-core/ze_core/orchestration/state.py`
- [x] **T004** Implement stall detector, caps, `stalled`/`replanned`/`ask_user` ledger writes, inject stall context into retry `prior_outputs` if companion omitted it · `core/contracts/ze-agents/ze_agents/delegate.py`

**Checkpoint**: Engine can cap flailing without companion prompts.

---

## Phase 3: User Story 1 — Stall then ask (P1) 🎯 MVP

**Goal**: One silent retry, then user-visible ask.

- [x] **T005** [US1] Tests: empty/error response is stall; successful response is not; retry `prior_outputs` nonempty · `core/engine/ze-core/tests/orchestration/test_delegate.py`
- [x] **T006** [US1] On block, tool result requires ask; ledger `ask_user` · `core/contracts/ze-agents/ze_agents/delegate.py`

**Checkpoint**: US1 testable.

---

## Phase 4: User Story 2 — Caps / non-conductor paths (P1)

- [x] **T007** [US2] Turn cap 6 blocks further delegates · `core/engine/ze-core/tests/orchestration/test_delegate.py`
- [x] **T008** [US2] Confirmation / `awaiting_confirmation` is not stall; speech-act one-shot under cap · `core/engine/ze-core/tests/orchestration/test_delegate.py`
- [x] **T009** [US2] Graph parallel compound tests still gather without stall wrapper · `core/engine/ze-core/tests/orchestration/nodes/test_execution.py`

**Checkpoint**: US2 testable.

---

## Phase 5: User Story 3 — Trace honesty (P2)

- [x] **T010** [US3] Trace copy includes new statuses (154 panel may already print raw status) · `core/engine/ze-core/tests/orchestration/test_message_trace.py`
- [x] **T011** [P] [US3] Companion instructions: one silent retry then ask · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [x] **T012** [P] [US3] Eval or scenario id `conductor_stall_then_ask` · `eval/scenarios/conductor.yaml`

**Checkpoint**: US3 testable.

---

## Phase 6: Polish

- [x] **T013** Grep: no workflow/goal insert on stall path; no `plan_sequential`; 151 fields intact
- [x] **T014** Validate: `make test-core` / personal companion tests as needed; ruff

---

## Dependencies & Execution Order

T001 → T002 → T003 → T004 → T005–T006 → T007–T009 → T010; T011 and T012 after T004 (different files, parallel). T013–T014 last.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T004, T005 |
| FR-002 | T002, T004, T005 |
| FR-003 | T002, T006, T007 |
| FR-004 | T004, T011 |
| FR-005 | T008, T009 |
| FR-006 | T003, T010 |
| FR-007 | T013 |
