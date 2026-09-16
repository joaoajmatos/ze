# Tasks: Promote Conductor Instance to Workflow/Goal

**Input**: Design documents from `/specs/phases/157-promote-conductor-instance/`

**Tests**: Required. Product code after 155 and 156 Implemented.

---

## Phase 1: Setup

- [x] **T001** Confirm 155/156 Implemented and `confirmation_timeout` / agent names `goals` and `workflow` · `apps/ze-api/ze_api/api/websocket/confirmation.py`

---

## Phase 2: Foundational

- [x] **T002** Fail-first: unfinished ledger ⇒ offer predicate true; all `done` ⇒ false; no store called · tests next to helper
- [x] **T003** Implement unfinished-ledger / should-offer helper · `core/engine/ze-core/ze_core/orchestration/` (or conversation helper module)

**Checkpoint**: Detector is testable without LLM.

---

## Phase 3: User Story 1 — Offer on unfinished / timeout (P1) 🎯 MVP

**Goal**: Offer, never silent insert.

- [x] **T004** [US1] Fail-first: `confirmation_timeout` with unfinished conductor does not create goal/workflow · `apps/ze-api/tests/api/test_ws_conformance.py`
- [x] **T005** [US1] Timeout/abort user copy offers promote when ledger unfinished · `apps/ze-api/ze_api/api/websocket/confirmation.py`
- [x] **T006** [US1] Companion: on turn-end unfinished, offer in the assistant reply; record offer on trace · `plugins/ze-personal/ze_personal/agents/companion/agent.py`

**Checkpoint**: US1 testable.

---

## Phase 4: User Story 2 — Keep going / create via delegate (P1)

- [x] **T007** [US2] Companion instructions: keep-going → `delegate_to_agent` `goals` or `workflow` with ledger in `prior_outputs`; 152 still applies · `plugins/ze-personal/ze_personal/agents/companion/agent.py`
- [x] **T008** [US2] Unit test: mocked companion/delegate create path; decline ⇒ 0 inserts · `plugins/ze-personal/tests/agents/companion/`
- [x] **T009** [US2] Goal vs workflow rule tests (ambiguous ⇒ no dual create) · companion tests

**Checkpoint**: US2 testable.

---

## Phase 5: User Story 3 — No procedures / no auto-offer on success (P1)

- [x] **T010** [US3] Test successful all-done conductor does not offer · companion or core tests
- [x] **T011** [US3] Grep/test promote modules never call `memory_procedures` · tests + polish grep
- [x] **T012** [P] [US3] Eval id `conductor_promote_offer_unfinished` · `eval/scenarios/conductor.yaml`

**Checkpoint**: US3 testable.

---

## Phase 6: Polish

- [x] **T013** Docs: conductor roadmap already lists 157; mention timeout offer if confirmation docs exist
- [x] **T014** Validate: api confirmation tests, personal companion tests, ruff; 151–156 pins held

---

## Dependencies & Execution Order

T001 → T002 → T003 → T004 → T005–T006 → T007–T009 (T007 before T008/T009, same companion file as T006 — sequential with T006). T010–T012 after create/offer behavior exists. T013–T014 last.

T006 and T007 share `companion/agent.py` — not parallel.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T003, T005, T006, T007 |
| FR-002 | T004, T005, T008 |
| FR-003 | T007, T009 |
| FR-004 | T007, T008 |
| FR-005 | T010 |
| FR-006 | T001, T014 |
| FR-007 | T011 |
