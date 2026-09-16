# Tasks: Eval `memory_proposals_count` Hard-Cut and Guide Phase-Index Honesty

**Input**: Design documents from `/specs/phases/150-eval-guide-honesty/`

**Tests**: Required. Fail-first.

---

## Phase 1: Setup

- [x] **T001** Grep remaining `memory_proposals_count` and `memory_proposals` (must not restore AgentResult field) · repo

---

## Phase 2: User Story 1 — Eval is tool_calls only (P1) 🎯 MVP

### Tests

- [x] **T002** [P] [US1] Fail-first: schema/OpenAPI omit `memory_proposals_count` · `apps/ze-api/tests/`

### Implementation

**⟶ Wait for T002, then:**

- [x] **T003** [US1] Delete field from `EvalChatResponse` · `apps/ze-api/ze_api/api/schemas.py`
- [x] **T004** [US1] Stop assigning the field · `apps/ze-api/ze_api/api/routes/eval.py`
- [x] **T005** [US1] Hard-cut MCP docs · `core/ops/ze-eval/ze_eval/server.py`
- [x] **T006** [US1] Hard-cut `docs/eval.md` table row
- [x] **T007** [US1] Regenerate `@ze/client` types (`bun run scripts/codegen.ts` or package script) · `packages/ze-client/`
- [x] **T008** [US1] Delete always-0 test assertions; do not keep a shim test that the field is 0 · tests

---

## Phase 3: User Story 2 — Guide indexes (P1)

- [x] **T009** [US2] Sync `AGENTS.md` phase index 140–150 to `specs/README.md`
- [x] **T010** [US2] Sync `CLAUDE.md` the same way; files MUST agree
- [x] **T011** [US2] Confirm no `specs/phases/151-*` directory

---

## Phase 4: Polish

- [x] **T012** Confirm this tree does not implement 144–149 product
- [x] **T013** Validate: `make test` (ze-api) + ze-eval tests if present; ruff on touched Python

## Waves

1. T001  
2. T002 then T003 then T004 then T005 ∥ T006 then T007 then T008  
3. T009 ∥ T010 then T011  
4. T012 then T013  
