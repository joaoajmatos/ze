# Tasks: Extractor Dual-Write and Dedup Races

**Input**: Design documents from `/specs/phases/148-extractor-dual-write/`

**Tests**: Required. Fail-first. Do not conflate 143 reply asserts with duplicate-row asserts.

---

## Phase 1: Setup

- [x] **T001** Confirm live `_remembered_predicates` uses `ToolCall.success` + predicate-only · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`

---

## Phase 2: Foundational

- [x] **T002** Add identity helper + `ok` payload parse in `ze_memory` · `core/cognition/ze-memory/ze_memory/fact_identity.py`

---

## Phase 3: User Story 1 — In-turn remember is not extracted again (P1) 🎯 MVP

### Tests

- [x] **T003** [P] [US1] Fail-first: remember `ok` + extract → one current identity · `core/engine/ze-core/tests/orchestration/nodes/test_extractor_dual_write.py`
- [x] **T004** [P] [US1] Fail-first: identity unit tests (normalize, different predicates not collapsed) · `core/cognition/ze-memory/tests/test_fact_identity.py`

### Implementation

**⟶ Wait for tests, then:**

- [x] **T005** [US1] Replace `_remembered_predicates` skip with `ok` + identity filter in `write_memory` · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`
- [x] **T006** [US1] Failed `remember_fact` does not uniquely force extract write; 140 admission still applies · tests

---

## Phase 4: User Story 2 — Tests name the failure (P1)

- [x] **T007** [US2] Keep 143 model-lie tests in companion honesty files; no duplicate-row asserts there · `plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py`
- [x] **T008** [US2] Duplicate-race tests assert cardinality, not “the model lied” · `test_extractor_dual_write.py`

---

## Phase 5: User Story 3 — One write rule (P2)

- [x] **T009** [US3] Confirm no hard non-LLM speech-act classifier module shipped · catalog review
- [x] **T010** [US3] Docs: same-turn remember vs extract · `docs/memory.md` / `specs/core/ze-memory.md`

---

## Phase 6: Polish

- [x] **T011** Validate: `make test-core test-memory test-personal`; ruff on touched files

## Waves

1. T001 then T002  
2. T003 ∥ T004 then T005 then T006  
3. T007 ∥ T008  
4. T009 then T010 then T011  
