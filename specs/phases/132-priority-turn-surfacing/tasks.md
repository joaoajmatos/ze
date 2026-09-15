---
description: "Task list for Priority Turn Surfacing (Phase 132)"
---

# Tasks: Priority Turn Surfacing

**Input**: Design documents from `/specs/phases/132-priority-turn-surfacing/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/turn_surfacing.md, quickstart.md

**Tests**: Included — constitution Principle V.

**Organization**: Foundational types/service → US1 inline mentions (P1) → US2 recap / what's-open (P2) → Polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Independent within its wave (different file, no incomplete dependency)
- **[US#]**: User story from spec.md

## Path Conventions

`core/arbitration/ze-priority/`, `core/engine/ze-core/`, `core/contracts/ze-agents/`, `apps/ze-api/ze_api/container.py`. See plan.md Project Structure.

---

## Phase 1: Setup

*No setup tasks.* No new package, dependency, or migration.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared mention type, score-time relevance fields, merged-snapshot reader, and composition-root injection. Both stories consume these.

**⚠️ CRITICAL**: Finish this phase before US1 or US2.

**Wave 1 — independent (different files):**

- [x] **T001** Add `OpenItemMention` and additive `PriorityItem` fields `linked_entity_ids`, `match_text`, `hedge` (data-model.md) · `core/arbitration/ze-priority/ze_priority/types.py`

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T002** Fill `linked_entity_ids` / `match_text` / `hedge` in `score_hypothesis`, `score_goal`, and `score_relationship_staleness` (research.md R3, R10) · `core/arbitration/ze-priority/ze_priority/scoring.py`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 — independent (different files):**

- [x] **T003** [P] Extend scoring unit tests so hypothesis/goal/relationship items carry the new fields · `core/arbitration/ze-priority/tests/test_scoring.py`
- [x] **T004** [P] Add `TurnSurfacing` with merged snapshot (`rank()` + `merge()`), `recap_mentions()`, `is_global_open_query()`, and degrade-to-empty on `ZePriorityError` / degrade-to-unmerged-rank if override store fails (contracts/turn_surfacing.md, FR-009) · `core/arbitration/ze-priority/ze_priority/turn.py`

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4 — independent (different files):**

- [x] **T005** [P] Tests: recap order follows merge including a pin; total ranking failure returns `[]`; override-store failure still returns ranked items (FR-002, FR-009, SC-003/SC-004) · `core/arbitration/ze-priority/tests/test_turn.py`
- [x] **T006** [P] Construct `TurnSurfacing` in the composition root and put it on `config["configurable"]["turn_surfacer"]`; keep `loop_surfacer` for push eligibility · `apps/ze-api/ze_api/container.py`

**Checkpoint**: Merged snapshot can be read without the graph node. User stories can start.

---

## Phase 3: User Story 1 - A turn mentions the most deserving relevant item (Priority: P1) 🎯 MVP

**Goal**: Unsolicited inline mentions are relevance-gated, follow merged `PriorityView` order (including pins), stay ≤ 3 items, and never inject an unrelated global top item. No loop-only fallback.

**Independent Test**: spec.md User Story 1 Independent Test / SC-001, SC-002, SC-004.

### Tests

**Wave 1 — independent (different files):**

- [x] **T007** [P] [US1] Tests: overlapping loop+goal with goal ranked/pinned higher mentions the goal first; unrelated global top item absent; empty when no overlap; cap of 3; unconfirmed hypothesis is hedged; no call path to `LoopSurfacer.inline_candidates` (FR-001–FR-003, FR-010, FR-011) · `core/arbitration/ze-priority/tests/test_turn.py`
- [x] **T008** [P] [US1] Rewrite `surface_loops` tests to inject `turn_surfacer.inline_mentions`; missing surfacer / no entities / exception / empty mentions still return `{}`; component type is `open_items`; `final_response` append still works on non-compound turns · `core/engine/ze-core/tests/orchestration/nodes/test_loop_surfacing.py`

**⟶ Wait for Wave 1 to finish, then:**

### Implementation

**Wave 2 — independent (different files):**

- [x] **T009** [P] [US1] Implement `inline_mentions`: graph `has_open_loop` overlap for loops, `linked_entity_ids` for hypotheses, `match_text` for goals/relationships; filter after merge; cap 3; hedged text; log `worldstate_loop_inline:{id}` for loop mentions (research.md R3–R5, R8–R10) · `core/arbitration/ze-priority/ze_priority/turn.py`
- [x] **T010** [P] [US1] Switch `surface_loops` to `turn_surfacer.inline_mentions(entity_ids, entities=...)`; skip append when `is_global_open_query(prompt)`; emit `open_item_mentions` + `open_items` component; never call `loop_surfacer` (contracts/turn_surfacing.md) · `core/engine/ze-core/ze_core/orchestration/nodes/loop_surfacing.py`

**Checkpoint**: User Story 1 is independently testable. MVP.

---

## Phase 4: User Story 2 - "What's open" and resume recap use the same ranking (Priority: P2)

**Goal**: Resume recap's "Still open" slice is merged `PriorityView` order. An explicit what's-open question injects that list into the system prompt. Workflows stay a separate recap section. One failed source does not fail the turn.

**Independent Test**: spec.md User Story 2 Independent Test / SC-003.

**Wave 1 — independent (different files):**

- [x] **T011** [P] [US2] Add runtime-only `AgentContext.open_priorities_note` (data-model.md) · `core/contracts/ze-agents/ze_agents/types.py`
- [x] **T012** [P] [US2] Tests for `is_global_open_query` (positive/negative prompts) · `core/arbitration/ze-priority/tests/test_turn.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — independent (different files):**

- [x] **T013** [P] [US2] Prepend `open_priorities_note` in `_build_system_prompt` immediately after `resume_recap` · `core/contracts/ze-agents/ze_agents/base_agent.py`
- [x] **T014** [P] [US2] Reshape `ResumeRecap` to `open_item_lines` from `turn_surfacer.recap_mentions()` (drop `loop_surfacer` + `goal_store.list_active()`); on what's-open prompts set `open_priorities_note` from the same recap list (FR-004, FR-005, research.md R6–R7) · `core/engine/ze-core/ze_core/orchestration/nodes/context.py`

**⟶ Wait for Wave 2 to finish, then:**

- [x] **T015** [US2] Resume-recap tests: mixed items appear in rank order, not loops-then-goals; workflows still listed; missing `turn_surfacer` still completes the turn. What's-open tests: `open_priorities_note` set, `surface_loops` does not also append (FR-004, FR-005, FR-009) · `core/engine/ze-core/tests/orchestration/nodes/test_context.py`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Wave 1 — independent (different files):**

- [x] **T016** [P] Close the "Surfacing consumer" open question in `specs/arch/attention-arbitration.md` as resolved by this phase
- [x] **T017** [P] Set spec **Status** to Implemented and update the phase index row · `specs/phases/132-priority-turn-surfacing/spec.md`, `specs/README.md`, `CLAUDE.md`

**⟶ Wait for Wave 1 to finish, then:**

- [x] **T018** `make test-priority && make test-core && make lint` — validate SC-001–SC-004 (quickstart.md)

---

## Dependencies & Execution Order

- **Setup**: skipped
- **Foundational (T001–T006)** blocks both stories
- **US1 (T007–T010)** depends on Foundational; MVP; does not need US2
- **US2 (T011–T015)** depends on Foundational (`recap_mentions`, `is_global_open_query`); T010's skip-on-global-query is the only US1 coupling
- **Polish (T016–T018)** after both stories

Waves: Foundational 1→2→3→4. US1 tests then implementation. US2 context field / query tests, then prompt+fetch_context, then node tests.

## Notes

- No task adds a migration, REST route, or push-budget change (FR-006, FR-007, FR-008).
- `ze-core` must not gain a `ze-priority` import (Constitution III).
