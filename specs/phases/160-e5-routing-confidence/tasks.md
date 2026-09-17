# Tasks: E5 Routing Confidence

**Input**: Design documents from `/specs/phases/160-e5-routing-confidence/`

**Tests**: Required. Fail-first.

---

## Phase 1: Setup

- [x] **T001** Confirm `E5Embedder` + prefixes still default; YAML `gap_threshold: 0.03` exists; `defaults.py` still 0.55 / 0.10 · `core/engine/ze-core/ze_core/embeddings.py` + `ze_agents/defaults.py`

---

## Phase 2: Foundational

**Wave 1 — independent (different files):**

- [x] **T002** [P] Fail-first: `RouterConfig()` (no YAML) with E5-band clear winner is **not** `is_compound` — currently fails on 0.10 gap · `core/engine/ze-core/tests/routing/test_router.py`
- [x] **T003** [P] Fail-first: low-gap / below-floor fixtures still `is_compound`; Haiku `complete` not called from the router · `core/engine/ze-core/tests/routing/test_router.py`

**Checkpoint**: Red tests for US1/US2.

---

## Phase 3: User Story 1 — Clear single-agent skips decompose (P1) 🎯 MVP

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T004** [US1] Set `ROUTING_THRESHOLD` and `ROUTING_GAP_THRESHOLD` from E5 measurement (start from YAML 0.03 gap + compressed band); keep names · `core/contracts/ze-agents/ze_agents/defaults.py`

**⟶ Wait for T004, then:**

**Wave 2 — independent (different files):**

- [x] **T005** [P] [US1] Mirror the same pair in `config.yaml` `routing:`; comment that defaults own the values · `apps/ze-api/config/config.yaml`
- [x] **T006** [P] [US1] Settings/container tests: missing YAML block still uses E5 defaults · `apps/ze-api/tests/test_settings.py` / container wiring tests
- [x] **T007** [P] [US1] English + Portuguese clear-winner fixtures pass under `RouterConfig()` · `core/engine/ze-core/tests/routing/test_router.py`

**Checkpoint**: US1 testable.

---

## Phase 4: User Story 2 — True compound still decomposes (P1)

- [x] **T008** [US2] Close-score fixture still `is_compound`; decompose node tests unchanged · `core/engine/ze-core/tests/routing/` + `tests/orchestration/nodes/test_routing_nodes.py`
- [x] **T009** [US2] Grep: `apply_conductor_rewrite` / 153/155 tests not edited except deleting false-compound cases if any were MiniLM-gap artifacts · `core/engine/ze-core/tests/orchestration/`

**Checkpoint**: US2 testable.

---

## Phase 5: User Story 3 — Living docs name E5 (P2)

**Wave 3 — independent (different files):**

- [x] **T010** [P] [US3] Constitution Principle VII: `intfloat/multilingual-e5-base` + prefixes, not MiniLM · `.specify/memory/constitution.md`
- [x] **T011** [P] [US3] ADR `local-embeddings.md`: current decision is E5; MiniLM superseded · `specs/arch/local-embeddings.md`
- [x] **T012** [P] [US3] AGENTS + CLAUDE stack table + embeddings comment; `docs/architecture.md`; `specs/core/ze-core.md`; README 97 remainder · `AGENTS.md` `CLAUDE.md` `docs/` `specs/`

**Checkpoint**: US3 testable via grep.

---

## Phase 6: Polish

- [x] **T013** Optional `@pytest.mark.slow` live-E5 clear-match smoke; `make test-core`; ruff; no MiniLM-as-current in living docs

---

## Dependencies & Execution Order

T001 → T002–T003 (parallel) → T004 → T005–T007 (parallel) → T008–T009 → T010–T012 (parallel) → T013. T002 and T003 share `test_router.py` — sequential if the same class; otherwise T002 first then T003 in that file.

## Coverage

| FR | Tasks |
|---|---|
| FR-001 | T002, T004 |
| FR-002 | T005, T006 |
| FR-003 | T003, T008 |
| FR-004 | T009 |
| FR-005 | T001, T013 |
| FR-006 | T010, T011, T012 |
| FR-007 | T007, T008 |
