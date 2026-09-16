# Tasks: Memory Admission and Conversational Remember/Forget

**Input**: Design documents from `/specs/phases/140-memory-admission/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required (constitution V; spec Independent Tests). Fail-first where noted.

## Format

`- [ ] **T###** [P?] [US#] Description · path`

---

## Phase 1: Setup

**Wave 1 — independent:**

- [x] **T001** [P] Confirm `submit_perception_facts` is the only production fact persist used by `write_memory` · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`
- [x] **T002** [P] List companion `agent_module_paths` so new tools module can be registered first · `plugins/ze-personal/ze_personal/plugin.py`

---

## Phase 2: Foundational

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — extractor types (single file):**

- [x] **T003** Add closed `PredicateFamily` + keep/drop parse helpers in · `core/cognition/ze-memory/ze_memory/extractor.py`

**⟶ Wait for Wave 2, then:**

**Wave 3 — forget persist (store):**

- [x] **T004** Add private mark-contradicted persist for forget (no public `propose_facts`) · `core/cognition/ze-memory/ze_memory/retriever.py`

**Checkpoint**: Gate types exist; forget can hide a row from retrieval.

---

## Phase 3: User Story 1 — Empty/ephemeral turns do not pollute memory (P1) 🎯 MVP

**Goal**: Extractor returns `[]` unless a closed family durable fact.

**Independent Test**: Fixtures ephemeral / commitment / empty → `[]`; preference/constraint may emit.

### Tests

**Wave 4 — independent tests:**

- [x] **T005** [P] [US1] Fail-first unit tests for keep/drop families and commitment drop · `core/cognition/ze-memory/tests/test_extractor_admission.py`
- [x] **T006** [P] [US1] Eval YAML rows `ephemeral`, `constraint`, `commitment` · `eval/scenarios/memory.yaml`

### Implementation

**⟶ Wait for Wave 4 tests to exist, then:**

- [x] **T007** [US1] Rewrite `_SYSTEM` / parse path to keep/drop + closed families; commitments drop · `core/cognition/ze-memory/ze_memory/extractor.py`

**Checkpoint**: SC-001, SC-004, SC-005 (store-only constraint).

---

## Phase 4: User Story 2 — Remember that writes only after tool success (P1)

**Goal**: `remember_fact` on companion through the seam.

### Tests

**Wave 5:**

- [x] **T008** [P] [US2] Fail-first tests: seam submit, `PROMPT_SUPPLIED`, `reviewed=true`, no confirm on `ok: false` · `plugins/ze-personal/tests/agents/companion/test_memory_tools.py`

### Implementation

**⟶ Wait for Wave 5, then Wave 6:**

- [x] **T009** [US2] Implement `remember_fact` @tool · `plugins/ze-personal/ze_personal/agents/companion/tools.py`
- [x] **T010** [US2] Register tools on companion (`tools` list + plugin module path) · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [x] **T011** [US2] Companion instructions: confirm remember only after tool `ok` · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [x] **T012** [US2] Dedup extraction predicates already written this turn · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`
- [x] **T013** [US2] Eval YAML `remember` aligned with FR-006 · `eval/scenarios/memory.yaml`

**Checkpoint**: SC-002, SC-006.

---

## Phase 5: User Story 3 — Forget that retracts (P2)

### Tests

**Wave 7:**

- [x] **T014** [P] [US3] Fail-first forget match / miss / no false confirm · `plugins/ze-personal/tests/agents/companion/test_memory_tools.py`

### Implementation

**⟶ Wait, then:**

- [x] **T015** [US3] Implement `forget_fact` @tool using T004 persist · `plugins/ze-personal/ze_personal/agents/companion/tools.py`
- [x] **T016** [US3] Eval YAML `forget` · `eval/scenarios/memory.yaml`

**Checkpoint**: SC-003.

---

## Phase 6: User Story 4 — One explicit write door (P2)

### Tests

**Wave 8:**

- [x] **T017** [P] [US4] Update/remove `write_memory` tests that persisted `memory_proposals` · `core/engine/ze-core/tests/orchestration/nodes/test_memory.py`
- [x] **T018** [P] [US4] Update `AgentResult` unit tests · `core/contracts/ze-agents/tests/test_types.py`

### Implementation

**⟶ Wait, then Wave 9:**

- [x] **T019** [US4] Remove `memory_proposals` persist harvest from · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`
- [x] **T020** [US4] Remove `memory_proposals` field from · `core/contracts/ze-agents/ze_agents/types.py`
- [x] **T021** [US4] Grep repo `memory_proposals` in `*.py` — remaining hits only specs/history comments, not persist

**Checkpoint**: FR-007; specialists do not get remember tools.

---

## Phase 7: Polish

- [x] **T022** Run `make test-memory test-personal test-core test-agents` and `make lint` against Success Criteria

## Dependencies & Execution Order

Setup → Foundational (T003–T004) → US1 extractor → US2 remember tools → US3 forget → US4 hard-cut field (can start tests earlier but T019 after T012) → Polish.

US1 is MVP. US4 must not ship a dual door even if US3 slips.
