# Tasks: Earned Memory Confirmations and Precise Forget

**Input**: Design documents from `/specs/phases/143-memory-claim-honesty/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required (constitution V). Fail-first on gate and matcher.

---

## Phase 1: Setup

**Wave 1 — independent (different files):**

- [x] **T001** [P] Confirm `remember_fact` / `forget_fact` already return `{ok: true|false, ...}` and companion lists those tools · `plugins/ze-personal/ze_personal/agents/companion/tools.py`
- [x] **T002** [P] Confirm live `_retract_facts_matching` is substring-then-cosine-0.75-top-5 (to delete, not wrap) · `core/cognition/ze-memory/ze_memory/retriever.py`

---

## Phase 2: Foundational

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T003** Add companion honesty module with fallback copy constants (`I could not store that.` / `I could not forget that.`) and `enforce_memory_confirmations` stub that returns the input unchanged · `plugins/ze-personal/ze_personal/agents/companion/honesty.py`

**Checkpoint**: Module exists; stories can proceed (US2 does not import this file).

---

## Phase 3: User Story 1 — Earned confirmations on the turn path (P1) 🎯 MVP

**Goal**: The user-visible companion reply may claim remembered/forgotten only after the matching tool returned `ok` true. Streamed tokens must not skip the gate.

**Independent Test**: Model text “I’ll remember that” with no successful `remember_fact` → gated reply has no remembered confirmation; sink never received the lie first. With `{ok: true}`, confirmation may remain. Same for forget.

### Tests

**Wave 2 — independent (different files):**

- [x] **T004** [P] [US1] Fail-first: unearned remember/forget claims stripped; `ok` false not earned even if `ToolCall.success`; earned `ok` true may keep confirmation · `plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py`
- [x] **T005** [P] [US1] Fail-first: `run` applies the gate; buffered `token_sink` sees gated text only; `stream` is not tool-free `_client.stream` · `plugins/ze-personal/tests/agents/companion/test_companion_agent.py`

### Implementation

**⟶ Wait for Wave 2 to finish, then:**

- [x] **T006** [US1] Implement deterministic sentence gate (`ok` payload, strip/fallback, fail-closed mixed sentences) · `plugins/ze-personal/ze_personal/agents/companion/honesty.py`

**⟶ Wait for T006, then Wave 3:**

- [x] **T007** [US1] Buffer `ctx.token_sink` around `agentic_loop`, apply the gate to the returned text, flush gated text, set `AgentResult.response` · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**⟶ Wait for T007, then:**

- [x] **T008** [US1] Hard-cut `CompanionAgent.stream`: same gated `run` result (single-chunk yield allowed); delete raw `_client.stream` completion · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**⟶ Wait for T008, then:**

- [x] **T009** [US1] Hard-cut eval criteria that reward unearned “I’ll remember” (especially `memory_store_explicit_fact`) · `eval/scenarios/memory.yaml`

**Checkpoint**: SC-001, SC-002, SC-003, SC-006 for the companion turn path. MVP.

---

## Phase 4: User Story 2 — Precise forget match (P2)

**Goal**: Forget retracts a clearly identified biography fact or returns `ok` false. No short-substring or top-5 cosine over-forget.

**Independent Test**: Several seeded facts; query `mode` retracts none; exact `dark mode` retracts that row only; loose embedding neighbors do not batch-retract.

### Tests

**Wave 4:**

- [x] **T010** [P] [US2] Fail-first matcher table: exact identity, named value in query, reject short substring, reject cosine 0.75 top-5 batch, unique high-cosine single hit · `core/cognition/ze-memory/tests/test_forget_retract.py`

### Implementation

**⟶ Wait for Wave 4 to finish, then:**

- [x] **T011** [US2] Replace `_retract_facts_matching` with the contract ladder (delete substring/`in` and top-5 0.75; no flag) · `core/cognition/ze-memory/ze_memory/retriever.py`

**⟶ Wait for T011, then:**

- [x] **T012** [US2] Confirm `forget_fact` still maps empty ids to `{ok: false, error: "no matching fact"}` · `plugins/ze-personal/tests/agents/companion/test_memory_tools.py`

**Checkpoint**: SC-004, SC-005. Forget success is trustworthy enough for US1 confirmations.

---

## Phase 5: Polish

**⟶ Wait for Phases 3 and 4, then Wave 5 — independent (different files):**

- [x] **T013** [P] Document turn-path confirmation + precise forget (not prompt-only) · `docs/memory.md`
- [x] **T014** [P] Point living honesty follow-ons; do not start P5 · `specs/arch/memory-honesty-roadmap.md`
- [x] **T015** [P] Align `specs/core/ze-memory.md` / `specs/core/ze-agents.md` one-liners if they still describe prompt-only confirm or the old matcher

**⟶ Wait for Wave 5, then:**

- [x] **T016** Validate against Success Criteria: `make test-memory`, `make test-personal`, and `make lint` (no `companion.yml` validation hook)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2: T003)** blocks US1 implementation; US2 tests (T010) may start after Phase 1 because they touch `test_forget_retract.py` only.
- **US1 (Phase 3)** is the MVP: T004/T005 → T006 → T007 → T008 → T009 (T007 and T008 same file, sequential).
- **US2 (Phase 4)** is independently testable: T010 → T011 → T012.
- **Polish** after both stories.

### Waves (one line each)

1. T001 ∥ T002  
2. T003  
3. T004 ∥ T005 (US1 tests)  
4. T006 then T007 then T008 then T009  
5. T010 then T011 then T012 (US2; can overlap US1 after Phase 1)  
6. T013 ∥ T014 ∥ T015 then T016  

### Parallel example (US1 tests)

```text
T004 test_memory_claim_honesty.py
T005 test_companion_agent.py
```

### Implementation strategy

MVP = Phase 1–3 (earned confirmations). Ship US2 in the same feature so forgotten `ok` true is not an over-retract. Do not implement 144+ from the honesty roadmap.
