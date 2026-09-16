# Tasks: Mixed Gather+Act → Conductor

**Input**: Design documents from `/specs/phases/155-mixed-gather-act-conductor/`

**Tests**: Required. Product code after 154 Implemented. Do not implement 156/157 here.

---

## Phase 1: Setup

- [x] **T001** Confirm 153 `apply_conductor_rewrite` exists and 154 eval ids still grep-able · `core/engine/ze-core/ze_core/orchestration/nodes/routing.py`

---

## Phase 2: Foundational

**Wave 1 — fail-first tests (same file, sequential):**

- [x] **T002** Fail-first: mixed sequential-false research `read` + messenger `create` rewrites to companion; all-read compound does not · `core/engine/ze-core/tests/orchestration/test_nodes.py`
- [x] **T003** Fail-first: calendar `read` + messenger `create` rewrites (not a two-name list); two `create` sequential-false does not · `core/engine/ze-core/tests/orchestration/test_nodes.py`

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T004** Add gather/act intent helpers + widen `apply_conductor_rewrite` per contract · `core/engine/ze-core/ze_core/orchestration/nodes/routing.py`

**Checkpoint**: Foundation ready — rewrite tests can pass.

---

## Phase 3: User Story 1 — Research then mail (P1) 🎯 MVP

**Goal**: Mixed gather+act reaches companion; no parallel fan-out.

- [x] **T005** [US1] Cover `send` alias as act; sequential true mixed still rewrites · `core/engine/ze-core/tests/orchestration/test_nodes.py`
- [x] **T006** [US1] If decompose node tests pin sequential-only rewrite, update them so mixed sequential-false also sets hint/ledger · `core/engine/ze-core/tests/orchestration/nodes/test_routing_nodes.py`
- [x] **T007** [US1] Add eval `conductor_mixed_gather_act_research_messenger` (sequential false; companion primary) · `eval/scenarios/conductor.yaml`

**Checkpoint**: US1 independently testable.

---

## Phase 4: User Story 2 — Independent reads / single-domain (P1)

**Goal**: No conductor steal.

- [x] **T008** [US2] Keep existing all-read and one-subtask tests green; add news+research sequential-false identity if missing · `core/engine/ze-core/tests/orchestration/test_nodes.py`

**Checkpoint**: US2 testable.

---

## Phase 5: User Story 3 — Intent families (P2)

**Goal**: Classification table, not agent names.

- [x] **T009** [US3] Table-driven tests for lookup/search gather aliases and unknown/`manage` unclassified · `core/engine/ze-core/tests/orchestration/test_nodes.py`

**Checkpoint**: US3 testable.

---

## Phase 6: Polish

- [x] **T010** Grep: no `plan_sequential`; no `{research, messenger}`-only allowlist; 151 fields intact
- [x] **T011** Confirm 154 eval ids still present
- [x] **T012** Validate: `make test-core` targeting routing/nodes tests; ruff

---

## Dependencies & Execution Order

T001 → T002 → T003 → T004 → T005–T006 → T007 (eval file may proceed after T004) → T008 → T009 → T010–T012.

T002–T003, T005, T008, T009 share `test_nodes.py` — never parallel. T006 and T007 are different files from each other and from T004.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T002, T004, T007 |
| FR-002 | T001, T005 |
| FR-003 | T002, T008 |
| FR-004 | T003, T005, T009 |
| FR-005 | T003, T010 |
| FR-006 | T006, T007, T011 |
| FR-007 | T010 |
