# Tasks: Constraint Veto on Gated Writes

**Input**: Design documents from `/specs/phases/144-constraint-veto-mail-calendar/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required (constitution V). Fail-first on gate, matcher, and earned claims.

---

## Phase 1: Setup

**Wave 1 — independent (different files):**

- [x] **T001** [P] Confirm `HarnessHook.on_tool_start` / `register_hook` in bootstrap and `ToolSpec` lives in `ze_agents.tool` · `core/contracts/ze-agents/ze_agents/tool.py`
- [x] **T002** [P] Confirm reviewed constraint rows are `reviewed=true` and `contradicted=false` on `memory_facts` · `core/cognition/ze-memory/ze_memory/policies.py`

---

## Phase 2: Foundational

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T003** Add `constraint_gate` (default false) and optional `constraint_describe` on `@tool` / `ToolSpec` · `core/contracts/ze-agents/ze_agents/tool.py`

**⟶ Wait for T003, then:**

- [x] **T004** Add `ConstraintWriteView` + matcher + `HarnessHook` that skips unmarked tools, caches reviewed constraints on the turn, allow/confirm/refuse without executing the tool on block · `core/cognition/ze-memory/ze_memory/constraint_veto.py`

**⟶ Wait for T004, then:**

- [x] **T005** Register the hook at composition root (not from a plugin importing `ze_core`) · `core/engine/ze-core/ze_core/bootstrap.py`

**Checkpoint**: Dummy gated tool can be blocked; `remember_fact` unmarked is not.

---

## Phase 3: User Story 1 — One write gate plugins can join (P1) 🎯 MVP

**Goal**: A marked write is always checked. An unmarked write is not. Core has no mail-name list.

**Independent Test**: Test-double tool with `constraint_gate=True` (not `send_email`) violates a seeded reviewed constraint → no complete. Same tool unmarked → completes. `remember_fact` unmarked → completes.

### Tests

**Wave 2:**

- [x] **T006** [P] [US1] Fail-first: marked dummy tool blocked/confirmed; unmarked dummy and `remember_fact` not intercepted · `core/cognition/ze-memory/tests/test_constraint_veto.py`

### Implementation

**⟶ Wait for Wave 2, then:**

- [x] **T007** [US1] Conservative matcher (time window in user timezone, channel tokens, party names ≥ 3 chars); email-only does not auto-hit calendar; ambiguous → confirm · `core/cognition/ze-memory/ze_memory/constraint_veto.py`

**Checkpoint**: SC-001 and SC-006 (dummy tool) for the shared gate.

---

## Phase 4: User Story 2 — In-tree adopters (P1)

**Goal**: Mail send, calendar mutations, reminder writes go through the gate. Prospecting send is `send_email`.

**Independent Test**: Seed reviewed constraint; `send_email` / calendar write / `set_reminder` that violate do not complete silently.

### Tests

**Wave 3 — independent:**

- [x] **T008** [P] [US2] Fail-first: `send_email` / `draft_email` person-level never-contact · `plugins/ze-messenger/tests/`
- [x] **T009** [P] [US2] Fail-first: `create_event` / `update_event` / `delete_event` · `plugins/ze-calendar/tests/`
- [x] **T010** [P] [US2] Fail-first: `set_reminder` / `cancel_reminder` · `plugins/ze-calendar/tests/`

### Implementation

**⟶ Wait for Wave 3, then Wave 4 — independent marks:**

- [x] **T011** [P] [US2] Mark `send_email`; `draft_email` as spec (time-window ignore, person-level confirm) · `plugins/ze-messenger/ze_messenger/agents/messenger/tools.py`
- [x] **T012** [P] [US2] Mark `create_event`, `update_event`, `delete_event` · `plugins/ze-calendar/ze_calendar/agents/calendar/tools.py`
- [x] **T013** [P] [US2] Mark `set_reminder`, `cancel_reminder` · `plugins/ze-calendar/ze_calendar/agents/reminders/tools.py`

**⟶ Wait for Wave 4, then:**

- [x] **T014** [US2] Document/test that prospecting outbound send is `send_email` (do not gate `add_prospect`) · `plugins/ze-prospecting/tests/`

**Checkpoint**: SC-002, SC-003.

---

## Phase 5: User Story 3 — Earned veto language (P2)

**Goal**: “I won’t send because of your constraint” only after `veto` true. Companion instructions no longer defer the veto.

### Tests

**Wave 5:**

- [x] **T015** [P] [US3] Fail-first: unearned veto claim stripped; `veto` true may keep; sink gated · `plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py`

### Implementation

**⟶ Wait for T015, then:**

- [x] **T016** [US3] Enforce earned veto claims on companion turn path (reuse token_sink buffer) · `plugins/ze-personal/ze_personal/agents/companion/honesty.py`

**⟶ Wait for T016, then:**

- [x] **T017** [US3] Apply the same helper on messenger/calendar/reminders `run` if those agents emit constraint-refusal prose; buffer sinks · plugin agent `run` methods

**⟶ Wait for T017, then:**

- [x] **T018** [US3] Hard-cut companion instructions that say do not block mail/calendar this turn · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**Checkpoint**: SC-004, SC-005.

---

## Phase 6: Polish

**⟶ Wait for Phases 3–5, then Wave 6 — independent:**

- [x] **T019** [P] Document the write gate (not a mail-only if-list) · `docs/memory.md`
- [x] **T020** [P] Point roadmap 144 as shipped-when-implemented; do not start 145 in this tree · `specs/arch/memory-honesty-roadmap.md`

**⟶ Wait for Wave 6, then:**

- [x] **T021** Validate: `make test-agents test-memory test-personal test-calendar test-messenger` and `make lint` on touched packages (no `companion.yml` `owns: validation`)

---

## Dependencies & Execution Order

- Setup → Foundational (T003–T005) blocks every story.
- US1 dummy gate is MVP.
- US2 adopter marks after the hook exists.
- US3 claims after tools can return `veto`.
- Polish last.

### Waves (one line each)

1. T001 ∥ T002  
2. T003 then T004 then T005  
3. T006 then T007  
4. T008 ∥ T009 ∥ T010 then T011 ∥ T012 ∥ T013 then T014  
5. T015 then T016 then T017 then T018  
6. T019 ∥ T020 then T021  
