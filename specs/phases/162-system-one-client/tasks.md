# Tasks: System One Client

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V, FR-008). Fail-first. Default suites never POST to OpenRouter.

**Pin**: `POST {openrouter_base_url}/systemone`, model `typesafe/jev-1.13`, `OPENROUTER_API_KEY`. No `typesafe-sdk`, no chat completions, no `TYPESAFE_API_KEY`.

---

## Phase 1: Setup

**Purpose**: Shared dep and default-off config.

**Wave 1 — independent (different files):**

- [x] **T001** [P] Add `httpx==0.28.1` to ze-core dependencies · `core/engine/ze-core/pyproject.toml`
- [x] **T002** [P] Add `system_one:` block (`enabled: false`, `model: typesafe/jev-1.13`, `timeout_ms: 2000`, `surfaces: {}`); do not put an API key in YAML · `apps/ze-api/config/config.yaml`

---

## Phase 2: Foundational

**Purpose**: Protocol types and empty `judgments` on the trace. Blocks every story.

**⚠️** No user-story work until this phase is complete.

**Wave 1 — fail-first tests (different files):**

- [x] **T003** [P] Fail-first: noul/choice/score question dataclasses, `SystemOneResult` skip vs ok, Protocol is not `LLMClient` · `core/contracts/ze-agents/tests/test_system_one.py`
- [x] **T004** [P] Fail-first: `MessageTrace.judgments` defaults to `[]`; two `JudgmentTrace` rows with exactly one `consumed=True` round-trip via `asdict` · `core/engine/ze-core/tests/orchestration/nodes/test_trace_judgments.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — independent (different files):**

- [x] **T005** [P] Add `SystemOneQuestion` / `SystemOneAnswer` / `SystemOneResult` / `SystemOneClient` Protocol (`evaluate(state, questions)`) with wire types `noul`/`choice`/`score` · `core/contracts/ze-agents/ze_agents/system_one.py`
- [x] **T006** [P] Add `JudgmentTrace` and `MessageTrace.judgments` default `[]` · `core/engine/ze-core/ze_core/conversation/messages/types.py`

**⟶ Wait for Wave 2 to finish, then:**

- [x] **T007** Initialize `judgments: []` each turn so checkpointed lists do not leak · `core/engine/ze-core/ze_core/orchestration/state.py`, `core/engine/ze-core/ze_core/conversation/turn.py`

**Checkpoint**: Types import; tests for T003–T004 pass; no HTTP yet.

---

## Phase 3: User Story 1 — Typed question, typed answer (P1) 🎯 MVP

**Goal**: A caller asks noul/choice/score and reads probabilities without parsing LLM JSON. Plugins type against `ze_sdk`.

**Independent Test**: Fake or mocked-HTTP client; noul `0.9` is a float; choice has label + map + peakedness; `from ze_sdk import SystemOneClient` does not import `ze_core`.

### Tests

**Wave 1 — independent (different files):**

- [x] **T008** [P] [US1] Fail-first: mock HTTP 200 maps noul/choice/score answers, reported `model`, `usage.input_tokens`; never calls `/chat/completions` · `core/engine/ze-core/tests/openrouter/test_system_one.py`
- [x] **T009** [P] [US1] Fail-first: `from ze_sdk import SystemOneClient` equals `ze_agents.system_one.SystemOneClient` · `packages/ze-sdk/tests/test_imports.py`

**⟶ Wait for Wave 1 to finish, then:**

### Implementation

**Wave 2 — independent (different files):**

- [x] **T010** [P] [US1] Implement `OpenRouterSystemOneClient.evaluate` success path: `POST {base_url}/systemone`, model `typesafe/jev-1.13`, Bearer `OPENROUTER_API_KEY`, same referer/title as chat; `CostTracker.record` on `outcome="ok"` using reported model id · `core/engine/ze-core/ze_core/openrouter/system_one.py`
- [x] **T011** [P] [US1] Re-export `SystemOneClient` next to `NLIClient` · `packages/ze-sdk/ze_sdk/__init__.py`

**Checkpoint**: US1 independently testable (`make test-core` client tests, `make test-sdk`). No production graph caller.

---

## Phase 4: User Story 2 — Timeout / missing key does not change the turn (P1)

**Goal**: Disabled, missing key, timeout, 429/529, and invalid payload skip; the graph does not raise; admission and routing stay on the pre-162 path.

**Independent Test**: `evaluate` returns `outcome="skip"` and a closed `skip_reason`; a turn with enabled+empty key still completes.

### Tests

- [x] **T012** [US2] Fail-first: skip `disabled`, `missing_key`, `timeout`, `overload` (429/529), `error`, `invalid_request` (empty questions/state) — no exception · `core/engine/ze-core/tests/openrouter/test_system_one.py`

**⟶ Wait for T012, then:**

### Implementation

- [x] **T013** [US2] `DisabledSystemOneClient` plus fail-open mapping inside `evaluate` (never raise into the graph); empty payload does not POST · `core/engine/ze-core/ze_core/openrouter/system_one.py`

**⟶ Wait for T013, then:**

**Wave 2 — independent (different files):**

- [x] **T014** [P] [US2] Construct live or disabled client from YAML + `openrouter_api_key`; put `SystemOneClient` on `dep_map` · `core/engine/ze-core/ze_core/bootstrap.py`
- [x] **T015** [P] [US2] Hold `system_one_client` on the container; set `configurable["system_one_client"]` · `apps/ze-api/ze_api/container.py`

**⟶ Wait for Wave 2 to finish, then:**

- [x] **T016** [US2] Default-off injects disabled client; enabled + blank key skips and does not crash startup; no judgments written when nobody called evaluate · `core/engine/ze-core/tests/` and/or `apps/ze-api/tests/` (container/bootstrap)

**Checkpoint**: US2 independently testable. FR-009 still holds (no extractor/router edits).

---

## Phase 5: User Story 3 — Trace can show what was judged (P2)

**Goal**: `MessageTrace.judgments` round-trips through JSONB, REST, WS, and the trace panel. Skips are visible; unused answers are `consumed=false`.

**Independent Test**: Construct a trace with two judgments, one consumed; skip row has `skip_reason` and null answer; empty list hides the panel section.

### Tests

**Wave 1 — independent (different files):**

- [x] **T017** [P] [US3] Fail-first: `record_trace` copies `state["judgments"]`; skip row is not a fake high noul · `core/engine/ze-core/tests/orchestration/nodes/test_trace_judgments.py`
- [x] **T018** [P] [US3] Fail-first: `judgments` on `MessageTraceResponse` and `WsTraceUpdateFrame` · `apps/ze-api/tests/api/test_judgments_trace_schema.py`

**⟶ Wait for Wave 1 to finish, then:**

### Implementation

**Wave 2 — independent (different files):**

- [x] **T019** [P] [US3] Copy `state["judgments"]` into `MessageTrace` in `record_trace` · `core/engine/ze-core/ze_core/orchestration/nodes/trace.py`
- [x] **T020** [P] [US3] Add `JudgmentTraceResponse` and `judgments: list = []` on REST + WS schemas; map in `_trace_to_response` · `apps/ze-api/ze_api/api/schemas.py`, `apps/ze-api/ze_api/api/messages.py`

**⟶ Wait for Wave 2 to finish, then:**

- [x] **T021** [US3] `make codegen` so `@ze/client` includes `judgments` · `packages/ze-client/src/generated/`

**⟶ Wait for T021, then:**

- [x] **T022** [US3] `JudgmentsSection` (hide when empty); wire `TraceEntry`, `toTraceFrame`, `EMPTY_TRACE`; vitest consumed vs skip · `apps/ze-web/src/widgets/trace-panel/ui/JudgmentsSection.tsx`, `TraceEntry.tsx`, `TraceContent.tsx`, `apps/ze-web/src/features/trace-state/lib/toTraceFrame.ts`

**Checkpoint**: US3 independently testable (`make test-core`, `make test`, `make test-web`). Production turns still persist `[]`.

---

## Phase 6: Polish

**Wave 1 — independent (different files):**

- [x] **T023** [P] Document `SystemOneClient` beside `NLIClient` · `specs/core/ze-agents.md`
- [x] **T024** [P] Document OpenRouter System One HTTP impl · `specs/core/ze-core.md`
- [x] **T025** [P] Grep: no `TYPESAFE_API_KEY` in runtime code; no `typesafe-sdk`; `evaluate` not on `LLMClient`; extractor/router/skills/retrieval/push/dream untouched (FR-009, FR-010) · repo grep

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T026** Validate against Success Criteria: `make test-agents`, `make test-sdk`, `make test-core`, `make test`, `make test-web`, `make lint` (no live vendor; SC-001–SC-005)

---

## Dependencies & Execution Order

Setup (T001–T002) → Foundational (T003–T004 then T005–T006 then T007) → US1 (T008–T009 then T010–T011) → US2 (T012 → T013 → T014–T015 → T016) → US3 (T017–T018 then T019–T020 then T021 then T022) → Polish (T023–T025 then T026).

T008 and T012 share `core/engine/ze-core/tests/openrouter/test_system_one.py` — sequential. T010 and T013 share `ze_core/openrouter/system_one.py` — sequential. T004 and T017 share `test_trace_judgments.py` — sequential.

### User story independence

- **US1**: Typed `evaluate` + SDK. No DI required for the unit tests.
- **US2**: Fail-open + DI. Does not need the trace panel.
- **US3**: Trace/UI. Can use constructed `JudgmentTrace` lists without a live evaluate.

### Parallel opportunities

- T001 ∥ T002
- T003 ∥ T004
- T005 ∥ T006
- T008 ∥ T009
- T010 ∥ T011
- T014 ∥ T015
- T017 ∥ T018
- T019 ∥ T020
- T023 ∥ T024 ∥ T025

### MVP

Phase 1 + 2 + US1 (T001–T011). Stop and validate typed answers + SDK import before fail-open/DI and trace UI.

---

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T003, T005, T010, T014, T015 |
| FR-002 | T009, T011 |
| FR-003 | T001, T010 |
| FR-004 | T002, T014 |
| FR-005 | T002, T012, T013 |
| FR-006 | T012, T013, T016 |
| FR-007 | T004, T006, T017, T019, T020, T022 |
| FR-008 | T003, T008, T012, T026 |
| FR-009 | T016, T025, T026 |
| FR-010 | T008, T010, T025 |
