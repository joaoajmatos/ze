# Tasks: Fat Delegate ACI

**Input**: Design documents from `/specs/phases/151-fat-delegate-aci/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required (constitution V). Fail-first.

---

## Phase 1: Setup

**Wave 1 — independent (different files):**

- [x] **T001** [P] Grep `delegate_to_agent` listings and `"task"` / `"context"` on delegate call sites; list files this phase must hard-cut · repo
- [x] **T002** [P] Snapshot companion class `description` so this tree cannot change embeddings · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

---

## Phase 2: Foundational

**⟶ Wait for Wave 1, then Wave 2 — sequential (same test file):**

- [x] **T003** Fail-first: schema required `agent_name`+`objective`; properties omit `task`/`context`; max depth 1 · `core/engine/ze-core/tests/orchestration/test_delegate.py`
- [x] **T004** Fail-first: non-companion caller and target `companion` fail without `run` · `core/engine/ze-core/tests/orchestration/test_delegate.py`

**⟶ Wait for Wave 2, then Wave 3 — harness implementation (same files, sequential):**

- [x] **T005** Hard-cut `DELEGATE_TOOL_SCHEMA` and prompt assembly (`objective`, `prior_outputs`, `inputs`, `output_shape`, `stop_condition`) · `core/contracts/ze-agents/ze_agents/delegate.py`
- [x] **T006** Pass `self.name` into `run_delegate`; enforce companion-only caller, non-companion target, depth 1 · `core/contracts/ze-agents/ze_agents/base_agent.py`
- [x] **T007** Keep `{response, tool_calls}` result; inherit `gate_decision`; isolated `messages` · `core/contracts/ze-agents/ze_agents/delegate.py`

**Checkpoint**: Fat ACI and refuse rules exist; stories can use them.

---

## Phase 3: User Story 1 — Fat brief + speech-act still works (P1) 🎯 MVP

**Goal**: Companion can brief a specialist with the fat ACI. Speech-act one-shots work with `objective` only. Nested `tool_calls` still earn 146 confirmations. Specialist transcripts stay off session `messages`.

**Independent Test**: `run_delegate` from companion with fat fields; speech-act tests pass `objective`; 146 nested cancel payloads still visible.

### Tests

**Wave 4 — sequential then independent:**

- [x] **T008** [US1] Fail-first: fat fields appear in worker prompt; omitted optionals do not · `core/engine/ze-core/tests/orchestration/test_delegate.py`

**⟶ After T008 (same-file join), then:**

- [x] **T009** [P] [US1] Fail-first: companion/speech-act tests use `objective` not `task`; nested domain tools still earn confirmations · `plugins/ze-personal/tests/agents/companion/`

### Implementation

**⟶ Wait for Wave 4, then Wave 5:**

- [x] **T010** [US1] Companion instructions: `delegate_to_agent` uses `objective` and may pass optional fat fields; do not edit `description` · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [x] **T011** [US1] Update remaining 146/honesty tests and prompt strings that still pass `task`/`context`; 151 contract supersedes 146’s `task` wording (do not reopen 146 product) · `plugins/ze-personal/tests/`

**Checkpoint**: US1 independently testable. Companion `description` matches T002 snapshot.

---

## Phase 4: User Story 2 — Only companion conducts (P1)

**Goal**: Research and other specialists do not list or successfully call `delegate_to_agent`. Depth 1 cannot re-delegate. Research does not guess the calendar.

**Independent Test**: Research `tools` omit the name; research instructions lack `delegate_to_agent`; depth-1 refuse test green.

### Tests

**Wave 6 — independent (different files):**

- [x] **T012** [P] [US2] Fail-first: every registered agent except companion omits `delegate_to_agent` from `tools` · `plugins/ze-personal/tests/agents/research/` or a registry test
- [x] **T013** [US2] Fail-first: depth 1 `run_delegate` fails · `core/engine/ze-core/tests/orchestration/test_delegate.py`

### Implementation

**⟶ Wait for Wave 6, then Wave 7:**

- [x] **T014** [US2] Remove `delegate_to_agent` from research `tools`; replace calendar-delegate copy with the limitation · `plugins/ze-personal/ze_personal/agents/research/agent.py`
- [x] **T015** [US2] Delete or rewrite research tests that stub nested delegate · `plugins/ze-personal/tests/agents/research/`

**Checkpoint**: US2 independently testable. No agent other than companion lists the tool.

---

## Phase 5: User Story 3 — Do not steal routing (P2)

**Goal**: Graph sequential path and companion embeddings stay as they are. Worker still inherits parent `gate_decision`.

**Independent Test**: `after_decompose` sequential → `plan_sequential`; companion `description` lock; inherit-gate test still passes.

**Wave 8:**

- [x] **T016** [P] [US3] Lock test: sequential compound still routes to `plan_sequential` · `core/engine/ze-core/tests/orchestration/test_edges.py`
- [x] **T017** [P] [US3] Lock test: companion `description` unchanged vs T002; `run_delegate` still copies `gate_decision` · tests

**Checkpoint**: This tree did not start 152/153.

---

## Phase 6: Polish

**Wave 9:**

- [x] **T018** Grep: no remaining delegate `task`/`context`; no 152 CapabilityGate in `run_delegate`; no graph node deletes · repo
- [x] **T019** Validate: `make test-core` (or ze-core + ze-personal tests covering delegate/companion/research) and ruff on touched Python

---

## Dependencies & Execution Order

Setup (T001–T002) → Foundational tests (T003–T004) → harness (T005–T007) → US1 (T008–T011) → US2 (T012–T015) → US3 locks (T016–T017) → Polish (T018–T019).

Same-file `test_delegate.py` tasks are sequential within a file; do not parallel T003/T004/T008/T013 as simultaneous writes — they share that file (T003+T004 listed together as one file: implement as one ordered edit). T010 must not touch `description`.

## Parallel Opportunities

T001 ∥ T002. After harness: T009 ∥ T010 if tests vs agent.py. T012 ∥ T013. T016 ∥ T017. T014 after T012.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T003, T005, T018 |
| FR-002 | T007, T008 |
| FR-003 | T012, T014 |
| FR-004 | T004, T006, T013 |
| FR-005 | T009, T010, T011 |
| FR-006 | T014, T015 |
| FR-007 | T002, T016, T017, T018 |
| FR-008 | T007, T017 |
