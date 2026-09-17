# Tasks: Concurrent Thread Identity

**Input**: Design documents from `/specs/phases/159-concurrent-thread-identity/`

**Tests**: Required. Fail-first.

---

## Phase 1: Setup

- [x] **T001** Confirm 99 multiplexer + per-thread busy still in `connection.py`; 4000 test exists · `apps/ze-api/tests/api/test_ws.py`

---

## Phase 2: Foundational

**Wave 1 — independent (different files):**

- [x] **T002** [P] Fail-first: `trace_update` for thread B does not become the visible trace while A is active · `apps/ze-web/src/features/trace-state/`
- [x] **T003** [P] Fail-first: cancel/command with two pendings only drops A · `apps/ze-api/tests/api/`

**Checkpoint**: Red tests for US1/US2.

---

## Phase 3: User Story 1 — Per-thread trace (P1) 🎯 MVP

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — independent (different files):**

- [x] **T004** [P] [US1] Key trace store by `thread_id`; `useTraceSocket` ignores or buckets other threads · `apps/ze-web/src/features/trace-state/`
- [x] **T006** [P] [US1] Codegen/WS types: `trace_update.thread_id` required if not already · `packages/ze-client/`

**⟶ Wait for Wave 2 to finish, then:**

- [x] **T005** [US1] Trace panel / ConductorSection reads active session’s trace only · `apps/ze-web/src/widgets/trace-panel/`

**Checkpoint**: US1 testable.

---

## Phase 4: User Story 2 — Cancel / promote thread (P1)

**Wave 3 — independent (different files):**

- [x] **T007** [P] [US2] `handle_command` requires `thread_id`; abort that thread’s token + that thread’s pending `request_id`s only · `apps/ze-api/ze_api/api/websocket/commands.py` + `endpoint.py`
- [x] **T008** [P] [US2] Confirmation timeout / 157 offer frames include `thread_id` · `apps/ze-api/ze_api/api/websocket/confirmation.py`

**⟶ Wait for Wave 3 to finish, then:**

- [x] **T009** [US2] Dual-thread busy: B still accepts messages while A is in conductor · existing `test_ws` / new test

**Checkpoint**: US2 testable.

---

## Phase 5: User Story 3 — 4000 pin (P2)

**Wave 4 — independent (different files):**

- [x] **T010** [P] [US3] Keep 4000 displace test; assert `selectSession` does not `reconnect()` · `apps/ze-web` + `test_ws.py`
- [x] **T011** [P] [US3] README: 99 transport shipped; remainder is 159 · `specs/README.md`

---

## Phase 6: Polish

- [x] **T012** `make test-web` trace tests; `make test` WS/confirmation; ruff; 151–158 greps unchanged

---

## Dependencies & Execution Order

Setup (T001) → Foundational red tests (T002–T003, parallel) → US1 store/types then panel (T004/T006 then T005) → US2 command+timeout then dual-busy (T007–T008 then T009) → US3 pin (T010–T011, parallel) → Polish (T012). T004 and T002 share `trace-state` — T002 first.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T002, T004, T005 |
| FR-002 | T003, T007 |
| FR-003 | T008 |
| FR-004 | T001, T009 |
| FR-005 | T010 |
| FR-006 | T001, T012 |
