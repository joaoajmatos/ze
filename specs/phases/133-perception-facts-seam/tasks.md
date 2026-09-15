---
description: "Task list for Perception Facts onto the Contribution Seam (Phase 133)"
---

# Tasks: Perception Facts onto the Contribution Seam

**Input**: Design documents from `/specs/phases/133-perception-facts-seam/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/perception-facts-seam.md, quickstart.md

**Tests**: Included — constitution Principle V.

**Organization**: EvidenceRef + submit helper (foundation) → US1 write_memory → US2 MemorySink → US4 goal-learning → US3 inbound/onboarding → Polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent within its wave (different file, no incomplete dependency)
- **[US#]**: User story from spec.md

## Path Conventions

See plan.md Project Structure.

---

## Phase 1: Setup

*No setup tasks.* No new package, dependency, or migration.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Citation kinds on `EvidenceRef`, `fact_to_contribution`, per-fact `submit_perception_facts` with `write=` persist callback. Blocks every call-site story.

**⚠️ CRITICAL**: Finish this phase before US1–US4.

**Wave 1 — independent (different files):**

- [x] **T001** [P] Extend `EvidenceRef.kind` with `"ingestion"` and `"goal"`; skip dangling checks for those kinds when no checker is supplied (research.md R4) · `core/contracts/ze-plugin/ze_plugin/contribution.py`
- [x] **T002** [P] Add failing tests for `fact_to_contribution` stamps (`PERCEPTION`/`FACT`/provenance/target_face/content) and for license rejection before persist · `core/cognition/ze-memory/tests/test_contribution.py`

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T003** Implement `fact_to_contribution` and `submit_perception_facts` / `PerceptionFactSubmit`: per-fact `submit_and_detect_collisions`, `producer_kind="fact"`, persist via `_write_fact_with_contradiction_check` returning UUID; do **not** set `Fact.provenance="synthesized"` for envelope `SYNTHESIZED` (research.md R1–R2) · `core/cognition/ze-memory/ze_memory/contribution.py`

**⟶ Wait for Wave 2 to finish, then:**

- [x] **T004** Wire collision_store/nli from the memory store when present (same getattr pattern as `ingest_signal`) · `core/cognition/ze-memory/ze_memory/retriever.py`

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4 — independent (different files):**

- [x] **T005** [P] Tests: dangling `fact` evidence still fails; `ingestion`/`goal` evidence without checkers succeeds; mixed license reject · `core/contracts/ze-plugin/tests/` (existing contribution tests) and `core/cognition/ze-memory/tests/test_contribution.py`
- [x] **T006** [P] Re-export submit helper from `ze_sdk.memory` for plugin/onboarding/automation callers · `packages/ze-sdk/ze_sdk/memory.py`

**Checkpoint**: A test can submit one perception fact through the seam without any listed call site changing yet. `propose_facts` still on Protocol.

---

## Phase 3: User Story 1 - Conversation facts enter memory only through the seam (Priority: P1) 🎯 MVP

**Goal**: `write_memory` extracted vs explicit facts go through the helper; provenance per surviving predicate after merge.

**Independent Test**: spec.md US1 / SC-001, SC-002, SC-005.

### Tests

**Wave 1 — independent (different files):**

- [x] **T007** [P] [US1] Tests: extracted-only → `SYNTHESIZED`; explicit-only → `PROMPT_SUPPLIED`; mixed batch per-predicate after merge; node does not call ungated `propose_facts`; wrong claim_kind rejected · `core/engine/ze-core/tests/orchestration/nodes/test_memory.py`

**⟶ Wait for Wave 1 to finish, then:**

### Implementation

- [x] **T008** [US1] Stamp provenance from explicit predicate set after `gather_fact_proposals` / `merge_fact_proposals`; call `submit_perception_facts` with `TargetFace.USER` · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`

**Checkpoint**: US1 independently testable. MVP.

---

## Phase 4: User Story 2 - Ingested document facts cite the ingestion (Priority: P1)

**Goal**: `MemorySink.push` converts strings to facts, seam + `SYNTHESIZED` + `WORLD`, `ingestion_id` on evidence/`source_refs`. Extractors and loop hook unchanged.

**Independent Test**: spec.md US2 / SC-003.

### Tests

**Wave 1 — independent (different files):**

- [x] **T009** [P] [US2] Rewrite sink tests: empty list no-op; UUID ingestion_id on `source_refs` and `EvidenceRef(kind="ingestion")`; no ungated `propose_facts` from sink · `core/ops/ze-ingestion/tests/test_sink.py`

**⟶ Wait for Wave 1 to finish, then:**

### Implementation

- [x] **T010** [US2] Implement `MemorySink.push` via `submit_perception_facts`; leave `loop_extractor` as-is; do not edit FinanceIngestionExtractor · `core/ops/ze-ingestion/ze_ingestion/sink.py`

**Checkpoint**: US2 independently testable.

---

## Phase 5: User Story 4 - Goal-learning promotion uses the same seam (Priority: P1)

**Goal**: `_promote_learnings` is synthesized perception with goal evidence; not ACTION/REFLECTION; keep swallow-on-failure.

**Independent Test**: spec.md US4 / FR-010.

### Tests

**Wave 1 — independent (different files):**

- [x] **T011** [P] [US4] Tests: no `propose_facts` from executor; `PERCEPTION`/`FACT`/`SYNTHESIZED`; `EvidenceRef(kind="goal")` and `source_refs`; skip when memory is None; swallow write errors · `core/automation/ze-automation/tests/goal_engine/test_executor_cross_goal.py`

**⟶ Wait for Wave 1 to finish, then:**

### Implementation

- [x] **T012** [US4] Route `_promote_learnings` through `submit_perception_facts` with goal citation · `core/automation/ze-automation/ze_automation/goals/executor.py`

**Checkpoint**: US4 independently testable. Public door no longer used by automation.

---

## Phase 6: User Story 3 - Inbound messages and onboarding seeds (Priority: P2)

**Goal**: Messenger inbound uses conversation-extraction stamps; onboarding `memory_fact` is `PROMPT_SUPPLIED` + `reviewed=True`.

**Independent Test**: spec.md US3.

### Tests

**Wave 1 — independent (different files):**

- [x] **T013** [P] [US3] Inbound extraction tests: seam + `SYNTHESIZED`; no ungated `propose_facts` · `plugins/ze-messenger/tests/` (existing inbound processor tests)
- [x] **T014** [P] [US3] Onboarding persistence tests: `PROMPT_SUPPLIED`, `reviewed=True`; profile_facet/plugin_setting unchanged · `core/ops/ze-onboarding/tests/` (existing persistence tests)

**⟶ Wait for Wave 1 to finish, then:**

### Implementation

**Wave 2 — independent (different files):**

- [x] **T015** [P] [US3] Route `_extract_facts` through the helper · `plugins/ze-messenger/ze_messenger/inbound/processor.py`
- [x] **T016** [P] [US3] Route `_apply_memory_fact` through the helper · `core/ops/ze-onboarding/ze_onboarding/persistence.py`

**Checkpoint**: All listed perception-fact writers are on the seam.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Wave 1 — independent (different files):**

- [x] **T017** [P] Confirm no production edits under `ze_priority/`, `loop_surfacing.py`, resume recap, `rank_subset`, push budget (FR-012) — grep + leave those files untouched · repo scan
- [x] **T018** [P] SDK re-export test if `ze_sdk` contribution/memory exports grew · `packages/ze-sdk/tests/`

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T019** Run quickstart suites: `make test-memory`, `make test-core`, `make test-ingestion` (or package pytest path in docs/testing.md), `make test-automation`, `make test-onboarding`, `make test-messenger`, `make lint` · repo root

---

## Dependencies & Execution Order

- Setup: empty
- Foundational (T001–T006) blocks all stories
- US1 (T007–T008) is MVP
- US2 (T009–T010) and US4 (T011–T012) can proceed in parallel after foundation (different packages)
- US3 (T013–T016) after foundation; independent of US1/US2/US4 except shared helper
- Polish last

Waves: same-file work is never parallel (T003 then T004 on helper/store; T008 after T007).
