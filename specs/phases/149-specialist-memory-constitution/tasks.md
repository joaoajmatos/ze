# Tasks: Specialist Memory Constitution

**Input**: Design documents from `/specs/phases/149-specialist-memory-constitution/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required (constitution V). Fail-first on prompt order, catalogs, instruction family, and unearned remember/forget success claims. Mock LLM and stores; no real OpenRouter or DB.

---

## Phase 1: Setup

**Wave 1 — independent (different files):**

- [x] **T001** [P] Confirm calendar, messenger, and news already call `_build_system_prompt` and do not define a local assembler · `plugins/ze-calendar/ze_calendar/agents/calendar/agent.py`
- [x] **T002** [P] Confirm `remember_fact` / `forget_fact` are absent from those three `tools` lists (do not add them) · `plugins/ze-messenger/ze_messenger/agents/messenger/agent.py`
- [x] **T003** [P] Confirm `enforce_memory_confirmations` lives in companion `honesty.py` and stays there (do not move into `ze_agents`) · `plugins/ze-personal/ze_personal/agents/companion/honesty.py`

---

## Phase 2: Foundational

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T004** Add `ze-personal` to `ze-news` dependencies so news can import the same honesty function (calendar/messenger already depend on it) · `plugins/ze-news/pyproject.toml`

**⟶ Wait for T004, then Wave 2 — independent (different files):**

- [x] **T005** [P] Confirm calendar and messenger can import `ze_personal.agents.companion.honesty` without a new package dep · those plugins’ `pyproject.toml`
- [x] **T006** [P] Leave companion agent on the existing honesty import (no `ze_agents.memory_honesty`) · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**Checkpoint**: One confirmation gate in companion honesty. News can import it. User stories can start. No specialist instruction edits yet.

---

## Phase 3: User Story 1 — Job and constitution lead (P1) 🎯 MVP slice A

**Goal**: Calendar, messenger, and news system prompts show shared constitution and that agent’s job **before** retrieved biography. Domain job text stays visible (ISO times, send rules, news grounding).

**Independent Test**: For each agent, identity builder injects `## Retrieved biography` plus a fact; assembled prompt has `## Memory constitution` before a unique job snippet, and that snippet before biography. Empty biography still starts with constitution + job.

### Tests

**Wave 3 — independent (different files):**

- [x] **T007** [P] [US1] Fail-first: calendar `_build_system_prompt` order (constitution, timezone/ISO job, then biography); empty biography still leads with constitution + job · `plugins/ze-calendar/tests/agents/calendar/test_calendar_agent.py`
- [x] **T008** [P] [US1] Fail-first: messenger prompt order (constitution, mail job, then biography) · `plugins/ze-messenger/tests/agents/messenger/test_messenger_agent.py`
- [x] **T009** [P] [US1] Fail-first: news prompt order (constitution, freshness/candidates job, then biography) · `plugins/ze-news/tests/agents/test_news_agent.py`

### Implementation

**⟶ Wait for Wave 3 to finish, then Wave 4 — independent (different files):**

- [x] **T010** [P] [US1] Keep calendar on shared `_build_system_prompt`; do not add a second builder; fix only if tests show an override or buried job · `plugins/ze-calendar/ze_calendar/agents/calendar/agent.py`
- [x] **T011** [P] [US1] Same for messenger · `plugins/ze-messenger/ze_messenger/agents/messenger/agent.py`
- [x] **T012** [P] [US1] Same for news (`_grounded_loop` system string) · `plugins/ze-news/ze_news/agents/agent.py`

**Checkpoint**: SC-001. Prompt order is testable per agent. MVP for US1.

---

## Phase 4: User Story 2 — No fake remember API (P1)

**Goal**: Those agents do not list `remember_fact` / `forget_fact`. User-visible replies do not claim remember/forget **tool** success. Retrieved facts may be applied silently. Not Phase 144 veto. Not Phase 145 recitation stripping.

**Independent Test**: Catalogs exclude the two tools. Mocked model text “I’ll remember that.” with no remember tool → `AgentResult.response` does not claim remember-tool success.

### Tests

**Wave 5 — independent (different files):**

- [x] **T013** [P] [US2] Fail-first: calendar `tools` excludes `remember_fact` and `forget_fact`; `run` (and stream) with unearned “I’ll remember that.” does not claim remember-tool success · `plugins/ze-calendar/tests/agents/calendar/test_calendar_agent.py`
- [x] **T014** [P] [US2] Fail-first: same catalog + unearned remember/forget success claims for messenger · `plugins/ze-messenger/tests/agents/messenger/test_messenger_agent.py`
- [x] **T015** [P] [US2] Fail-first: same for news · `plugins/ze-news/tests/agents/test_news_agent.py`

### Implementation

**⟶ Wait for Wave 5 to finish, then Wave 6 — independent (different files):**

- [x] **T016** [P] [US2] Import `enforce_memory_confirmations` from `ze_personal.agents.companion.honesty` and apply it to calendar `run` (and stream so it is not an ungated twin). Do not add remember tools · `plugins/ze-calendar/ze_calendar/agents/calendar/agent.py`
- [x] **T017** [P] [US2] Same for messenger · `plugins/ze-messenger/ze_messenger/agents/messenger/agent.py`
- [x] **T018** [P] [US2] Same for news grounded loop / `run` / `stream` · `plugins/ze-news/ze_news/agents/agent.py`

**Checkpoint**: SC-002, SC-003. Specialists cannot narrate a remember API they do not have.

---

## Phase 5: User Story 3 — One constitution family (P2)

**Goal**: Specialist jobs share companion’s 141 silent-use / no “I remember that you…” framing. No second memory-chat dialect. Prospecting, goals, and other specialists are not rewritten here.

**Independent Test**: Read calendar/mail/news instructions: silent use + no unsolicited recitation framing; they do not tell the model to confirm `remember_fact`. Other agents untouched.

### Tests

**Wave 7 — independent (different files):**

- [x] **T019** [P] [US3] Fail-first: calendar `_AGENT_INSTRUCTIONS` includes silent-use / no “I remember that you…” family and does not document remember/forget tools · `plugins/ze-calendar/tests/agents/calendar/test_calendar_agent.py`
- [x] **T020** [P] [US3] Fail-first: same family check for messenger instructions · `plugins/ze-messenger/tests/agents/messenger/test_messenger_agent.py`
- [x] **T021** [P] [US3] Fail-first: same family check for news instructions (news grounding rules still present) · `plugins/ze-news/tests/agents/test_news_agent.py`

### Implementation

**⟶ Wait for Wave 7 to finish, then Wave 8 — independent (different files):**

- [x] **T022** [P] [US3] Rewrite calendar job copy to the shared memory family; keep ISO-8601 / timezone job; do not add remember tools or 144 veto language as a product · `plugins/ze-calendar/ze_calendar/agents/calendar/agent.py`
- [x] **T023** [P] [US3] Same rewrite for messenger job copy; keep send/list rules · `plugins/ze-messenger/ze_messenger/agents/messenger/agent.py`
- [x] **T024** [P] [US3] Same rewrite for news job copy; keep store-grounding / freshness · `plugins/ze-news/ze_news/agents/agent.py`

**Checkpoint**: SC-004. One constitution family on the three named agents.

---

## Phase 6: Polish

**⟶ Wait for Phases 3–5, then Wave 9 — independent (different files):**

- [x] **T025** [P] Document specialist constitution + job order and no remember API on those catalogs; state 145 recitation reply-gate and 144 veto are not this phase · `docs/memory.md`
- [x] **T026** [P] Keep `specs/core/ze-agents.md` from claiming the honesty dialect lives in `ze_agents` · `specs/core/ze-agents.md`
- [x] **T027** [P] Confirm new plugin wiring does not import `ze_core`; news honesty import is `ze_personal` · `plugins/ze-news/ze_news/agents/agent.py`

**⟶ Wait for Wave 9, then:**

- [x] **T028** Validate against Success Criteria: `make test-personal test-calendar test-messenger test-news` and ruff on touched files

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2** → stories → Polish. News `ze-personal` dep (T004) blocks US2 implementation (T016–T018).
- **US1** (T007–T012) does not need the honesty import; can follow Foundational immediately.
- **US2** needs T004–T006 before T016–T018; tests T013–T015 can start after Foundational.
- **US3** is instruction-text; independent of the gate once catalogs are frozen. Prefer after US1 so job snippets used in order tests still match rewritten copy (re-run T007–T009 if job unique strings change).
- **Wave 1** independent. **T004** then **Wave 2**. **Wave 3** tests then **Wave 4**. **Wave 5** tests then **Wave 6**. **Wave 7** tests then **Wave 8**. **Wave 9** then **T028**.
- Do not implement Phase 144 veto, 145 recitation reply-path (beyond constitution framing already in US3), 146–148, or a `/memories` filesystem.
