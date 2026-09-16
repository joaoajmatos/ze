# Tasks: Forget vs Cancel Across Stores

**Input**: Design documents from `/specs/phases/146-forget-vs-cancel/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required (constitution V). Fail-first on extractor R14, label match, nested delegate, and confirmation gate.

---

## Phase 1: Setup

**Wave 1 — independent (different files):**

- [x] **T001** [P] Confirm `cancel_reminder`, `abandon_goal`, and `review.close_loop` / `drop_loop` already exist; companion lists `forget_fact` + `delegate_to_agent` and not `set_reminder` · `plugins/ze-personal/tests/agents/companion/test_speech_act_routing.py`
- [x] **T002** [P] Confirm live `run_delegate` sets `result` to the specialist response string (to delete, not wrap) · `core/contracts/ze-agents/ze_agents/delegate.py`
- [x] **T003** [P] Confirm extractor `_SYSTEM` lists `forget` without R14 cancel-vs-biography wording · `core/cognition/ze-memory/ze_memory/extractor.py`

---

## Phase 2: Foundational

**⟶ Wait for Wave 1 to finish, then Wave 2 — independent fail-first tests (different files):**

- [x] **T004** [P] Fail-first: `precise_label_match` unique / miss / ambiguous; short token does not substring-batch · `core/contracts/ze-agents/tests/test_label_match.py`
- [x] **T005** [P] Fail-first: `run_delegate` `result` is `{response, tool_calls}`; nested cancel payload visible · `core/engine/ze-core/tests/orchestration/test_delegate.py`
- [x] **T006** [P] Fail-first: “forget the dentist” (cancel) → `reminder` not `forget`; aisle-seat forget stays `forget`; facts `[]` · `core/cognition/ze-memory/tests/test_speech_act_gate.py`

**⟶ Wait for Wave 2 to finish, then Wave 3 — independent implementations (different files):**

- [x] **T007** [P] Implement `precise_label_match` (`Unique` / `Miss` / `Ambiguous`) per `contracts/precise-cancel-match.md` · `core/contracts/ze-agents/ze_agents/label_match.py`
- [x] **T008** [P] Hard-cut `run_delegate` result mapping; update in-tree delegate tests; no string-or-dict shim · `core/contracts/ze-agents/ze_agents/delegate.py`
- [x] **T009** [P] Extractor prompt: cancel/drop/abandon of reminder/loop/goal is that `speech_act`, not `forget`; R2 biography remains `forget` · `core/cognition/ze-memory/ze_memory/extractor.py`

**Checkpoint**: Shared match + nested tools + speech-act meaning exist; stories can use them.

---

## Phase 3: User Story 1 — Cancel speech hits the live store (P1) 🎯 MVP

**Goal**: Forget/cancel/drop/abandon aimed at a reminder, loop, or goal writes that store’s existing tool. Biography is not retracted. `forget_fact` is not dual-written for that utterance.

**Independent Test**: Seed a dentist reminder and an unrelated dentist-word fact. Utter “forget the dentist” as cancel. Reminder cancelled; fact live; no `forget_fact` `ok` true. Repeat for a loop (`close_loop`) and a goal (`abandon_goal`).

### Tests

**Wave 4 — independent (different files):**

- [x] **T010** [P] [US1] Fail-first: companion instructions require R14 handoff; cancel utterance must not call `forget_fact` when delegate/domain cancel is the path · `plugins/ze-personal/tests/agents/companion/test_speech_act_routing.py`
- [x] **T011** [P] [US1] Fail-first: reminders list → match → at most one `cancel_reminder`; two dentist labels + short query → no writes · `plugins/ze-calendar/tests/agents/reminders/test_cancel_match.py`
- [x] **T012** [P] [US1] Fail-first: loops agent lists then `close_loop` / `drop_loop` once on unique title match; miss/ambiguous writes nothing · `core/cognition/ze-worldstate/tests/test_loop_agent_cancel.py`

### Implementation

**⟶ Wait for Wave 4 to finish, then Wave 5 — independent (different files):**

- [x] **T013** [P] [US1] Add `loops` agent: list non-terminal loops, wrap `close_loop` / `drop_loop`; `import_agent_modules` + ze-api `ALL_AGENT_MODULE_PATHS` · `core/cognition/ze-worldstate/ze_worldstate/agents/`
- [x] **T014** [P] [US1] Reminders: list → `precise_label_match` → at most one `cancel_reminder`; update agent instructions · `plugins/ze-calendar/ze_calendar/agents/reminders/agent.py`
- [x] **T015** [P] [US1] Goals: list → match → at most one `abandon_goal`; update agent instructions · `core/automation/ze-automation/ze_automation/agents/goals/agent.py`

**⟶ Wait for Wave 5 to finish, then:**

- [x] **T016** [US1] Companion R14 instructions: forget-the-dentist → `delegate_to_agent` reminders/loops/goals; never `forget_fact` for that speech act; two named targets are two tools · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**⟶ Wait for T016, then:**

- [x] **T017** [US1] Eval: companion “forget the dentist” cancels reminder not biography; no dual-write criterion · `eval/scenarios/memory.yaml`

**Checkpoint**: SC-001, SC-004 for reminder/loop/goal cancel. MVP.

---

## Phase 4: User Story 2 — Biography forget stays biography-only (P1)

**Goal**: Named biography forget still uses `forget_fact` with Phase 143 precision. Unmatched reminders/loops/goals that share a word stay.

**Independent Test**: Seed “prefers aisle seats” and reminder “dentist.” “Forget that I like aisle seats” retracts the fact only.

### Tests

**Wave 6:**

- [x] **T018** [P] [US2] Fail-first: R2 utterance uses `forget_fact`; dentist reminder remains; vague “forget the dentist” with two reminders and no unique fact is miss/ask not batch-retract · `plugins/ze-personal/tests/agents/companion/test_speech_act_routing.py`

### Implementation

**⟶ Wait for Wave 6, then:**

- [x] **T019** [US2] Keep `forget_fact` + `_retract_facts_matching` unchanged; add instruction/test coverage that biography forget does not call domain cancel · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**Checkpoint**: SC-002. Closing the cancel door did not steal R2.

---

## Phase 5: User Story 3 — Forgotten claims stay earned (P2)

**Goal**: Domain cancel success may confirm the reminder/loop/goal action. It must not claim a forgotten biography fact unless `forget_fact` `ok` is true. Unearned cancel wording is stripped.

**Independent Test**: Cancel a reminder successfully; model says “I’ve forgotten that.” User-visible text has no forgotten-fact claim; may confirm the reminder was cancelled.

### Tests

**Wave 7 — independent (different files):**

- [x] **T020** [P] [US3] Fail-first: nested `cancel_reminder` success does not earn forgotten-fact claims; unearned “I’ve cancelled” stripped; `forget_fact` `ok` false still no forgotten claim · `plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py`
- [x] **T021** [P] [US3] Fail-first: `RemindersAgent` does not confirm cancel when `cancel_reminder` returns `error` · `plugins/ze-calendar/tests/agents/reminders/test_agent.py`

### Implementation

**⟶ Wait for Wave 7, then:**

- [x] **T022** [US3] Extend companion honesty: inspect nested `tool_calls`; `earned_forget` only from `forget_fact` `ok`; domain-claim strip per `contracts/earned-cancel-confirmation.md` · `plugins/ze-personal/ze_personal/agents/companion/honesty.py`

**⟶ Wait for T022, then Wave 8 — independent (different files):**

- [x] **T023** [P] [US3] Apply domain-claim strip on `RemindersAgent` `AgentResult.response` (direct routing) · `plugins/ze-calendar/ze_calendar/agents/reminders/agent.py`
- [x] **T024** [P] [US3] Apply domain-claim strip on `GoalAgent` `AgentResult.response` · `core/automation/ze-automation/ze_automation/agents/goals/agent.py`
- [x] **T025** [P] [US3] Apply domain-claim strip on `loops` `AgentResult.response` · `core/cognition/ze-worldstate/ze_worldstate/agents/`
- [x] **T026** [P] [US3] Eval criteria: cancel success must not praise forgotten biography; dual-write probe · `eval/scenarios/memory.yaml`

**Checkpoint**: SC-003. No second fake success after 143.

---

## Phase 6: Polish

**⟶ Wait for Phases 3–5, then Wave 9 — independent (different files):**

- [x] **T027** [P] Document R14 cancel vs `forget_fact`; nested delegate; unique-label cancel; 143 forgotten claims unchanged · `docs/memory.md`
- [x] **T028** [P] Align `specs/core/ze-memory.md` / `specs/core/ze-agents.md` one-liners for cancel vs forget · `specs/core/ze-memory.md`
- [x] **T029** [P] Point living honesty follow-ons; do not start 144 veto, 145 recitation, 147–150 · `specs/arch/memory-honesty-roadmap.md`

**⟶ Wait for Wave 9, then:**

- [x] **T030** Validate against Success Criteria: `make test-memory`, `make test-personal`, `make test-calendar`, `make test-automation`, `make test-worldstate`, `make test-agents`, and `make lint` (no `companion.yml` validation hook)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2: T004–T009)** blocks all stories.
- **US1 (Phase 3)** is the MVP: T010–T012 → T013–T015 → T016 → T017.
- **US2 (Phase 4)** after extractor R2 meaning (T009): T018 → T019 (same companion instructions file as T016 — run after T016).
- **US3 (Phase 5)** after nested delegate (T008) and US1 handoff: T020–T021 → T022 → T023–T024.
- **Polish** after stories.

### Waves (one line each)

1. T001 ∥ T002 ∥ T003  
2. T004 ∥ T005 ∥ T006 (fail-first foundations)  
3. T007 ∥ T008 ∥ T009  
4. T010 ∥ T011 ∥ T012 (US1 tests)  
5. T013 ∥ T014 ∥ T015 then T016 then T017  
6. T018 then T019 (US2; after T016)  
7. T020 ∥ T021 then T022 then T023 ∥ T024 ∥ T025 ∥ T026  
8. T027 ∥ T028 ∥ T029 then T030  

### Parallel example (US1 tests)

```text
T010 test_speech_act_routing.py
T011 test_cancel_match.py
T012 test_loop_agent_cancel.py
```

### Implementation strategy

MVP = Phase 1–3 (cancel hits the live store, no dual-write). Ship US2 in the same feature so R2 forget still works. Ship US3 so domain cancel is not a second unearned “I forgot.” Do not implement 144–145 or 147–150.
