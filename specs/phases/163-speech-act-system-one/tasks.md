# Tasks: Speech-Act System One

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V, FR-009). Fail-first. Default suites never call System One or an LLM endpoint.

**Pin**: Judgments go through 162's `SystemOneClient` (`configurable["system_one_client"]`). The LLM only words an admitted fact. Label filters stay `admit_speech_act` / `admit_family`. Do not start routing Choice (164).

---

## Phase 1: Setup

**Purpose**: Default-off config surface with documented, uncalibrated bars.

- [x] **T001** Add `system_one.surfaces.speech_act` (`enabled: false`; bars `act_min_peakedness`, `family_min_peakedness`, `biography_min` commented out and marked uncalibrated) · `apps/ze-api/config/config.yaml`

---

## Phase 2: Foundational

**Purpose**: Questions, thresholds, and the decision table. Blocks every story.

**⚠️** No user-story work until this phase is complete.

**Wave 1 — fail-first tests (one file, sequential with later test tasks):**

- [x] **T002** Fail-first: `thresholds_from_settings` is `None` unless `system_one.enabled`, the surface flag, and all three numeric bars are present; full config parses to `AdmissionThresholds` · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`

**⟶ Wait for T002, then:**

- [x] **T003** Implement the three questions (eight-way `speech_act` incl. Portuguese examples, `family`, `biography`), `AdmissionThresholds`, `AdmissionDecision`, `thresholds_from_settings`, `decide`, `judge_admission` (state is `{user, assistant[:1000]}`) · `core/cognition/ze-memory/ze_memory/speech_act_gate.py`

**Checkpoint**: Gate module imports; T002 passes; nothing calls it yet.

---

## Phase 3: User Story 1 — A timed reminder is not stored as biography (P1) 🎯 MVP

**Goal**: A timed remind utterance never becomes a biography fact; a durable preference still does.

**Independent Test**: Mocked System One returns `reminder` → `gather_fact_proposals` returns `[]` with no LLM call; returns `fact`/`preference`/high biography → one worded fact.

### Tests

- [x] **T004** [US1] Fail-first: timed reminder → `[]`, no LLM call; durable preference admitted and worded once with `agent` set; non-keep family holds · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`

**⟶ Wait for T004, then:**

### Implementation

- [x] **T005** [US1] Gate `gather_fact_proposals`: trivial turn / `[ERROR]` skip before System One; `hold` → `[]`; `admit` → `_word_admitted_facts` (family fixed, `_admit_parsed`); wording prompt `_WORDING_SYSTEM` · `core/cognition/ze-memory/ze_memory/extractor.py`

**Checkpoint**: US1 independently testable (`make test-memory`).

---

## Phase 4: User Story 2 — Cancel language is not forget-biography (P1)

**Goal**: "forget the dentist" (cancel a ping) is `reminder`, never `forget`; biography retract is `forget`; unknown labels are `drop`.

**Independent Test**: Gold-direction pair of fixtures plus an unknown label; none persists a fact.

### Tests

- [x] **T006** [US2] Fail-first: aisle-seat retract → `forget`, dentist cancel → `reminder`, both persist nothing; unknown label (`banana`) → drop, no LLM call · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`

**⟶ Wait for T006, then:** behavior comes from T003 (`admit_speech_act` is the only label filter) and T005. No new production code beyond tuning the `forget` / `reminder` criteria text in T003 if a fixture disagrees.

**Checkpoint**: US2 independently testable.

---

## Phase 5: User Story 3 — Unsure does not silently persist (P2)

**Goal**: Low peakedness or an even biography Noul holds; a System One skip runs the pre-163 judge exactly once; a hold never runs Haiku.

**Independent Test**: Low-peakedness and even-Noul fixtures return `[]` with the LLM untouched; a skip result runs the legacy extractor once; surface-off never calls System One.

### Tests

**Wave 1 — independent (different files):**

- [x] **T007** [P] [US3] Fail-first: low act peakedness holds with no Haiku tie-break; biography Noul `0.5` holds despite Choice `fact`; skip → legacy extractor awaited once; surface off → System One never called; trivial turn → System One never called · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`
- [x] **T008** [P] [US3] Fail-first: judgments from the gate land on the already-recorded `MessageTrace` (record_trace runs before write_memory) · `core/engine/ze-core/tests/orchestration/nodes/test_extractor_dual_write.py`

**⟶ Wait for Wave 1 to finish, then:**

### Implementation

- [x] **T009** [US3] Per-turn `admission_judgments` sink passed to the extractor; `_attach_admission_judgments` extends `state["message_trace"].judgments`; skip row carries `skip_reason`; only deciding questions are `consumed` · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`, `core/cognition/ze-memory/ze_memory/speech_act_gate.py`

- [x] **T010** [US3] Fail-first + verify: `consumed` flags (all three on a fact path; only `speech_act` when the act is not `fact`) · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`

**Checkpoint**: US3 independently testable (`make test-memory`, `make test-core`). Existing 148 dual-write tests still pass.

---

## Phase 6: Polish

**Wave 1 — independent (different files):**

- [x] **T011** [P] Spec status Implemented; phase index row; `CLAUDE.md` phase table · `specs/phases/163-speech-act-system-one/spec.md`, `specs/README.md`, `CLAUDE.md`
- [x] **T012** [P] Arch note O1 row notes the LLM only words admitted facts and the surface ships off · `specs/arch/system-one-models.md`
- [x] **T013** [P] Grep: routing, skill match, companion tool names, `admit_*`, contribution seam untouched (FR-007, FR-008) · repo grep

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T014** Validate against Success Criteria: `make test-memory`, `make test-core`, ruff on touched files (no live vendor; SC-001–SC-005)

---

## Out of phase (follow-up)

- [ ] **T015** Calibrate `act_min_peakedness`, `family_min_peakedness`, `biography_min` on Ze fixtures including Portuguese, then flip `speech_act.enabled`. FR-010 forbids shipping guessed bars, so this stays open until measured. · `apps/ze-api/config/config.yaml`

---

## Dependencies & Execution Order

Setup (T001) → Foundational (T002 then T003) → US1 (T004 then T005) → US2 (T006) → US3 (T007 ∥ T008, then T009, then T010) → Polish (T011 ∥ T012 ∥ T013, then T014). T015 is outside the phase.

T002, T004, T006, T007, T010 share `test_speech_act_system_one.py` — sequential. T003 and T009 both touch `speech_act_gate.py` — sequential.

### User story independence

- **US1**: Gate + extractor wiring. No trace work needed.
- **US2**: Fixtures over the same gate; no new wiring.
- **US3**: Hold/skip/trace behavior; trace can be tested with a hand-built sink.

### Parallel opportunities

- T007 ∥ T008
- T011 ∥ T012 ∥ T013

### MVP

Phase 1 + 2 + US1 (T001–T005). Stop and validate reminder-vs-fact before the hold, fallback, and trace work.

---

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T003, T004, T005, T006 |
| FR-002 | T003, T004 |
| FR-003 | T003, T006 |
| FR-004 | T003, T004, T007 |
| FR-005 | T003 |
| FR-006 | T005, T007 |
| FR-007 | T005, T007, T013 |
| FR-008 | T013, T014 |
| FR-009 | T002, T004, T014 |
| FR-010 | T001, T002, T015 |
