# Tasks: Speech-Act Routing Across Stores

**Input**: Design documents from `/specs/phases/142-speech-act-routing/`

**Prerequisites**: Phase 140 implemented. plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required. Table-driven R-rows.

---

## Phase 1: Setup

**Wave 1:**

- [x] **T001** Confirm Phase 140 `remember_fact` / `forget_fact` exist · `plugins/ze-personal/ze_personal/agents/companion/tools.py`
- [x] **T002** [P] Read `delegate_to_agent` contract · `core/contracts/ze-agents/ze_agents/delegate.py`

---

## Phase 2: Foundational

**⟶ Wait, then:**

- [x] **T003** Add `SpeechAct` enum · `core/cognition/ze-memory/ze_memory/types.py`

**Checkpoint**: Classifier has a typed target.

---

## Phase 3: User Story 1 — Timed remember is a reminder, not a fact (P1) 🎯 MVP

### Tests

**Wave 3:**

- [x] **T004** [P] [US1] Fail-first: R3/R8/R11 → no facts; speech_act reminder or loop · `core/cognition/ze-memory/tests/test_speech_act_gate.py`

### Implementation

**⟶ Wait, then Wave 4:**

- [x] **T005** [US1] Extend extractor JSON with `speech_act`; empty facts unless `fact` · `core/cognition/ze-memory/ze_memory/extractor.py`
- [x] **T006** [US1] Companion description + instructions: hand off timed acts; do not store as biography · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [x] **T007** [US1] Add `delegate_to_agent` to companion `tools` · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**Checkpoint**: SC-001, SC-002.

---

## Phase 4: User Story 2 — Durable remember/forget still hit fact tools (P1)

### Tests

**Wave 5:**

- [x] **T008** [P] [US2] R1/R2 still `remember_fact` / `forget_fact`; no reminder · `plugins/ze-personal/tests/agents/companion/test_speech_act_routing.py`

### Implementation

**⟶ Wait, then:**

- [x] **T009** [US2] Classifier maps standing preference to `fact` / `forget` · `core/cognition/ze-memory/ze_memory/extractor.py`
- [x] **T010** [US2] Companion instructions: R1/R2 use Phase 140 tools · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**Checkpoint**: SC-003.

---

## Phase 5: User Story 3 — Loops and goals (P2)

### Tests

**Wave 6:**

- [x] **T011** [P] [US3] R5 → loop, R6 → goal, zero facts · `core/cognition/ze-memory/tests/test_speech_act_gate.py`

### Implementation

**⟶ Wait, then:**

- [x] **T012** [US3] Map loop/goal acts; companion delegates to goal agent for R6 · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [x] **T013** [US3] Ensure post-turn extraction cannot admit R5/R6 as facts (T005 already) — add overlap test · `core/cognition/ze-memory/tests/test_speech_act_gate.py`

**Checkpoint**: SC-004.

---

## Phase 6: User Story 4 — Ingest, drop, constraint without veto (P3)

### Tests

**Wave 7:**

- [x] **T014** [P] [US4] R7 ingest not `remember_fact`; R10 drop; R9 constraint fact; mail tools still enabled · `plugins/ze-personal/tests/agents/companion/test_speech_act_routing.py`

### Implementation

**⟶ Wait, then:**

- [x] **T015** [US4] Classifier rows R7/R9/R10/R13; no silent fact on clarify · `core/cognition/ze-memory/ze_memory/extractor.py`
- [x] **T016** [US4] Eval YAML: reminder-timed, loop, goal plus existing five speech acts · `eval/scenarios/memory.yaml`
- [x] **T017** [US4] Document P5 veto as follow-up only (no tool gating) in companion instructions · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**Checkpoint**: SC-005, SC-006.

---

## Phase 7: Polish

- [x] **T018** Grep: no `set_reminder` added to news/prospecting/goals catalogs
- [x] **T019** Run `make test-memory test-personal` and `make lint`

## Dependencies & Execution Order

Setup → SpeechAct enum → US1 extractor+delegate (MVP) → US2 must not regress 140 tools → US3/US4 table rows → Polish.

Do not clone reminder tools onto companion (research.md).
