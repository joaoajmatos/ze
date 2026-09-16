# Tasks: Memory Read Contract and Prompt Constitution

**Input**: Design documents from `/specs/phases/141-memory-prompt-constitution/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required (constitution V).

---

## Phase 1: Setup

**Wave 1:**

- [x] **T001** [P] Inventory current `_build_system_prompt` order tests · `core/engine/ze-core/tests/orchestration/test_base_agent.py`
- [x] **T002** [P] Confirm `TurnSurfacing` has no fact-mention API to extend · `core/arbitration/ze-priority/ze_priority/turn.py`

---

## Phase 2: Foundational

**⟶ Wait, then Wave 2:**

- [x] **T003** Add `created_at` on `Fact` + `_fact_from_row` if missing · `core/cognition/ze-memory/ze_memory/types.py`
- [x] **T004** [P] Project `created_at` in · `core/cognition/ze-memory/ze_memory/projection.py`

**Checkpoint**: Formatter can show recency.

---

## Phase 3: User Story 1 — Always-on reviewed + formatted retrieval (P1) 🎯 MVP

### Tests

**Wave 3:**

- [x] **T005** [P] [US1] Fail-first: reviewed fact present despite low similarity; irrelevant pool not dumped · `core/cognition/ze-memory/tests/test_companion_policy_reviewed.py`
- [x] **T006** [P] [US1] Fail-first: `_format_memory` includes provenance, confidence, recency; no `"raw"` dialect · `core/engine/ze-core/tests/orchestration/test_base_agent.py`

### Implementation

**⟶ Wait, then Wave 4:**

- [x] **T007** [US1] Union reviewed facts first in · `core/cognition/ze-memory/ze_memory/policies.py`
- [x] **T008** [US1] Rewrite `_format_memory` · `core/contracts/ze-agents/ze_agents/base_agent.py`

**Checkpoint**: SC-001.

---

## Phase 4: User Story 2 — Constitution and job before biography (P1)

### Tests

**Wave 5:**

- [x] **T009** [P] [US2] Fail-first: constitution marker index < job < memory biography · `core/engine/ze-core/tests/orchestration/test_base_agent.py`

### Implementation

**⟶ Wait, then Wave 6:**

- [x] **T010** [US2] Reorder `_build_system_prompt` (constitution + job before identity memory) · `core/contracts/ze-agents/ze_agents/base_agent.py`
- [x] **T011** [US2] Split `build_identity_block` so memory is biography, not job · `plugins/ze-personal/ze_personal/persona/identity.py`
- [x] **T012** [US2] Shared constitution string (silent facts, no unsolicited recitation) · `core/contracts/ze-agents/ze_agents/base_agent.py`
- [x] **T013** [US2] Rewrite companion `_AGENT_INSTRUCTIONS` memory-use rules · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**Checkpoint**: SC-002, SC-005 (no specialist catalog rewrites).

---

## Phase 5: User Story 3 — No unsolicited fact mentions (P2)

### Tests

**Wave 7:**

- [x] **T014** [P] [US3] Assert `TurnSurfacing` tests still cover loops/goals only · `core/engine/ze-core/tests/orchestration/nodes/test_context.py`
- [x] **T015** [P] [US3] Companion instruction test: silent use, no “I remember that you” obligation · `plugins/ze-personal/tests/agents/companion/test_companion_agent.py`

### Implementation

**⟶ Wait, then:**

- [x] **T016** [US3] Do not add fact chips to `TurnSurfacing` / `surface_loops` (verify grep + comments if needed) · `core/arbitration/ze-priority/ze_priority/turn.py`

**Checkpoint**: SC-003, SC-004.

---

## Phase 6: Polish

- [x] **T017** Grep that calendar/mail/news/prospecting/goals agent instruction files are unchanged; run `make test-agents test-memory test-personal test-core` and `make lint`

## Dependencies & Execution Order

Setup → Fact.created_at → US1 policy+formatter → US2 prompt order (depends on T008/T010 same file — serialize T008 then T010) → US3 mention freeze → Polish.

Note: T008 and T010 both touch `base_agent.py` — never parallel.
