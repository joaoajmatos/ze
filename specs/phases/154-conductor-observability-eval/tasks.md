# Tasks: Conductor Observability and Eval

**Input**: Design documents from `/specs/phases/154-conductor-observability-eval/`

**Tests**: Required. Product code after 153 Implemented.

---

## Phase 1: Setup

- [ ] **T001** Confirm 153 `MessageTrace` ledger fields exist in spec/code at implement time · `core/engine/ze-core/ze_core/conversation/messages/types.py`

---

## Phase 2: Foundational

- [ ] **T002** Fail-first: OpenAPI/trace schema includes conductor hint + ledger + `request_id` · `apps/ze-api/tests/`
- [ ] **T003** Serialize ledger on REST + `trace_update`; regenerate `@ze/client` · schemas + codegen

**Checkpoint**: Clients can type the fields.

---

## Phase 3: User Story 1 — Trace panel (P1) 🎯 MVP

**Goal**: Panel shows plan, specialists, confirmation ids, ask/stall. Parallel turns do not fake a conductor plan.

- [ ] **T004** [P] [US1] Fail-first vitest: fixture conductor trace renders specialists + `request_id` · `apps/ze-web/src/widgets/trace-panel/`
- [ ] **T005** [US1] Conductor section in `TraceEntry` / `TraceContent`; omit when fields null · ze-web
- [ ] **T006** [US1] Independent parallel fixture: no conductor plan section · ze-web test

**Checkpoint**: US1 independently demoable.

---

## Phase 4: User Story 2 — Progress keys (P1)

**Goal**: Sequence-visible waiting copy.

- [ ] **T007** [US2] Add locale strings for `conductor.checking_calendar` and `conductor.drafting_mail` · companion/personal locales
- [ ] **T008** [US2] Emit those keys when companion starts calendar vs messenger delegates · `plugins/ze-personal/ze_personal/agents/companion/` + locale YAML (not hardcoded in `ze_core`)
- [ ] **T009** [US2] Unit test emit order calendar then mail · tests

**Checkpoint**: US2 testable without eval.

---

## Phase 5: User Story 3 — Four eval scenarios (P1)

**Goal**: YAML ids lock the product claims.

- [ ] **T010** [US3] Add `conductor_sequential_calendar_email` · `eval/scenarios/`
- [ ] **T011** [P] [US3] Add `routing_independent_parallel_not_companion` · `eval/scenarios/`
- [ ] **T012** [P] [US3] Add `conductor_speech_act_146_honest` · `eval/scenarios/`
- [ ] **T013** [US3] Add `conductor_mid_sequence_confirmation` · `eval/scenarios/`

**Checkpoint**: Grep finds all four ids. Criteria match FRs.

---

## Phase 6: Polish

- [ ] **T014** Docs: mention conductor trace if `docs/` describes the trace panel
- [ ] **T015** Grep: no `plan_sequential` restore; 151 fields intact
- [ ] **T016** Validate: `make test-core` / `make test` as needed, `make test-web`, ruff; codegen committed

---

## Dependencies & Execution Order

T001 → T002–T003 → T004–T006 → T007–T009 → T010–T013 → T014–T016.

Same-file eval YAML: T010 then T013 if one file; T011/T012 may be parallel files.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T002, T003, T004, T005, T006 |
| FR-002 | T007, T008, T009 |
| FR-003 | T010 |
| FR-004 | T011 |
| FR-005 | T012 |
| FR-006 | T013 |
| FR-007 | T015 |
