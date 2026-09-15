# Tasks: Memory Facts Hard-Cut onto Shared Claim Vocabulary

**Input**: Design documents from `/specs/phases/134-memory-facts-hard-cut/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included (constitution Principle V; spec Independent Tests). Prefer fail-first on type and SQL tests.

**Organization**: User stories from spec.md (US1 provenance dialect, US2 remove public door, US3 claim_kind on Fact).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3

## Path Conventions

Monorepo paths under `core/cognition/ze-memory/`, `apps/ze-api/`.

---

## Phase 1: Setup

**Purpose**: Confirm 133 contract and migration slot before editing runtime code

- [x] T001 Run the production `propose_facts(` grep from [quickstart.md](./quickstart.md). If a listed 133 call site still uses it as a **front door**, stop and record the blocker in the implementation notes — do not add a Protocol shim ([spec.md](./spec.md) FR-007, [contracts/memory-store.md](./contracts/memory-store.md))
- [x] T002 Create `core/cognition/ze-memory/ze_memory/migrations/versions/zm020_facts_doctrine_provenance.py` per [contracts/memory-facts-schema.md](./contracts/memory-facts-schema.md) (`down_revision = "zm019"` unless a newer `zm` revision already exists — then take the next id)

---

## Phase 2: Foundational

**Purpose**: Types + schema + persist INSERT so no path can still default to `raw`

**⚠️ CRITICAL**: User-story test updates depend on this

- [x] T003 Change `Fact` in `core/cognition/ze-memory/ze_memory/types.py`: `provenance: Provenance` (no `"raw"` default), add `claim_kind: ClaimKind`; keep `confidence: float` and `retrieval_provenance` ([data-model.md](./data-model.md) FR-001/FR-003)
- [x] T004 Remove `propose_facts` from `MemoryStore` in `core/cognition/ze-memory/ze_memory/store.py` ([contracts/memory-store.md](./contracts/memory-store.md) FR-006)
- [x] T005 Rename `PostgresMemoryStore.propose_facts` to `_persist_facts` in `core/cognition/ze-memory/ze_memory/retriever.py`; INSERT `provenance` and `claim_kind`; derive kind from 111 rule if omitted; compare `Provenance.SYNTHESIZED` not `"synthesized"`; raise typed `ZeError` on bad provenance
- [x] T006 [P] Update `_fact_from_row` in `core/cognition/ze-memory/ze_memory/projection.py` to parse `Provenance` / `ClaimKind`; delete `provenance=row_dict.get("provenance", "raw")`
- [x] T007 [P] Replace `COALESCE(provenance, 'raw')` with `provenance` in `core/cognition/ze-memory/ze_memory/policies.py`, `entity_anchor.py`, and `retrieval_rerank.py` (FR-002)
- [x] T008 [P] Add `provenance` to INSERT in `core/cognition/ze-memory/ze_memory/consolidation_store.py` (`synthesized` + `claim_kind='fact'` per data-model)
- [x] T009 Update dream decay / corroboration SQL consumers that branch on fact provenance strings in `core/cognition/ze-memory/ze_memory/dream/promoter.py` and `retriever.py` `_check_synthetic_corroboration` to use doctrine `'synthesized'` (value unchanged) and `Fact.provenance` enum in Python
- [x] T010 If Phase 133 `write=` still calls `propose_facts`, retarget to `_persist_facts` only (mechanical) in the 133 files (`ze_core/orchestration/nodes/memory.py`, `ze_ingestion/sink.py`, messenger inbound, onboarding persistence, `ze_automation/goals/executor.py`) — do **not** redesign those routes

**Checkpoint**: INSERT cannot land `raw`; Protocol has no `propose_facts`

---

## Phase 3: User Story 1 - Doctrine provenance, not `raw` (Priority: P1) 🎯 MVP

**Goal**: Rows and reads speak `Provenance`; quality diagnostic drops the `raw` bucket

**Independent Test**: Persist `prompt_supplied`, retrieve it, quality JSON has no `"raw"`; migration maps old `raw` → `prompt_supplied`

### Tests

- [x] T011 [P] [US1] Update/add tests in `core/cognition/ze-memory/tests/` (including `test_relevance_floor.py`, `test_entity_anchor.py`, store write tests) so fixtures use `Provenance.PROMPT_SUPPLIED` / `"prompt_supplied"` and assert missing provenance cannot insert
- [x] T012 [P] [US1] Update `apps/ze-api` fact-quality tests (and `MemoryFactQualityResponse` assertions) for [contracts/fact-quality-api.md](./contracts/fact-quality-api.md)

### Implementation

- [x] T013 [US1] Rewrite `get_fact_quality` in `apps/ze-api/ze_api/api/routes/memory.py` to group by doctrine provenance (no `raw_count`)
- [x] T014 [US1] Confirm `apps/ze-web/src/widgets/memory-feed/ui/MemoryFeedItem.tsx` synthesized badge still matches `"synthesized"`; no `raw` badge

**Checkpoint**: SC-001 / SC-002 / SC-005

---

## Phase 4: User Story 2 - No public ungated fact door (Priority: P1)

**Goal**: Production and Protocol have zero `propose_facts`

**Independent Test**: Grep Protocol and production; tests use `_persist_facts` or the seam

### Tests

- [x] T015 [P] [US2] Rewrite tests that call `store.propose_facts` in `core/cognition/ze-memory/tests/test_store_writes.py`, `core/engine/ze-core/tests/memory/test_store.py`, `core/ops/ze-ingestion/tests/test_sink.py`, `plugins/ze-messenger/tests/test_inbound_processor.py` to `_persist_facts` or 133 seam mocks — not a public alias

### Implementation

- [x] T016 [US2] Grep `propose_facts` repo-wide (`*.py`); remaining hits only `_persist_facts` definition, comments, or this spec directory
- [x] T017 [US2] Confirm `packages/ze-sdk/ze_sdk/memory.py` does not re-export a fact-write helper

**Checkpoint**: SC-003 / SC-006 (no shim)

---

## Phase 5: User Story 3 - Claim kind and shared confidence vocabulary (Priority: P2)

**Goal**: `Fact` round-trips `claim_kind`; decay still `TIME_LINEAR` on synthesized uncorroborated rows

**Independent Test**: Load a row into `Fact` with both enums; decay tests still pass

- [x] T018 [P] [US3] Add/update tests that `Fact.claim_kind` loads from SQL and that derivation uses `Provenance.SYNTHESIZED` + corroborated flag (111 rule) in `core/cognition/ze-memory/tests/`
- [x] T019 [US3] Verify `core/cognition/ze-memory/ze_memory/dream/promoter.py` still calls `ze_agents.claims.decay` / `TIME_LINEAR` with cliffs 0.50 / 0.25 (no second decay implementation)

**Checkpoint**: SC-004

---

## Phase 6: Polish

- [x] T020 [P] Update the `Fact` snippet in `docs/memory.md` if it still shows `provenance: str = "raw"`
- [x] T021 Update this spec header to Implemented and `specs/README.md` 134 row to ✅ **only in the implement phase** (not during spec-kit plan/tasks)
- [x] T022 Run `make test-memory` and `make test-api`; ruff on touched files (`plan.md` Technical Context)
- [x] T023 Re-run production `propose_facts(` grep from quickstart; must be clean
- [x] T024 Replace remaining `Fact(..., provenance="raw")` / `'raw'` constructors outside this spec dir (FR-012 compile breaks only — do not redesign events/episodes)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: T001 before any Protocol deletion if 133 is incomplete (blocker)
- **Foundational**: T002–T010; T003/T004/T005 sequential; T006–T008 [P] after T003
- **US1**: after Foundational (T007 SQL + T002 migration)
- **US2**: after T004/T005/T010
- **US3**: after T003/T005; can overlap US1 tests
- **Polish**: after stories

### User Story Dependencies

- US1 and US2 are both P1; Foundational delivers both doors (schema + Protocol). Do not ship Protocol deletion without INSERT provenance (T005) or rows stay `raw` via default until T002 drops it.
- US3 is dataclass completeness on the same persist path.

### Parallel Opportunities

- T006, T007, T008 after T003
- T011, T012
- T015, T018
- T020 vs T022

---

## Parallel Example: Foundational SQL

```bash
Task: "Update _fact_from_row in projection.py"
Task: "Replace COALESCE in policies.py, entity_anchor.py, retrieval_rerank.py"
Task: "INSERT provenance in consolidation_store.py"
```

---

## Implementation Strategy

### MVP

T001 → T002 → T003–T005 → T006–T009 → T011/T013 (provenance readable, no `raw`)

### Then

US2 test/grep (T015–T017) so the door is actually gone, then US3, then T022.

### Notes

- Do not migrate 133 call-site *routing* (already Contribution). Only retarget `write=` (T010).
- Do not commit unless the implementer is asked; spec-kit here prefers no commit.
- `zm020` id: if taken, next free `zm` revision.
