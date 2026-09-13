---

description: "Task list template for feature implementation"
---

# Tasks: User-Directed Priority Override

**Input**: Design documents from `specs/phases/127-priority-override/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included per Constitution Principle V (Test Discipline — NON-NEGOTIABLE): every feature ships tests; unit tests mock asyncpg/LLM, no real DB/LLM calls.

**Organization**: Tasks are grouped by user story (US1 = snapshot view, US2 = drag reorder, US3 = conversational reprioritization) per spec.md's priorities (P1, P1, P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)

## Path Conventions

Existing monorepo layout (plan.md "Project Structure"): `core/ze-priority/`,
`core/ze-collision/`, `apps/ze-api/ze_api/`, `apps/ze-web/src/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: New migration chain + package scaffolding for `ze-priority`'s first store

- [X] T001 Create `core/ze-priority/ze_priority/migrations/` directory and `zpri001_priority_overrides.py` — hand-written raw-SQL Alembic migration creating `priority_overrides` (columns per data-model.md's `PriorityOverride` table: `id`, `source_kind`, `source_id`, `anchor_source_kind`, `anchor_source_id`, `relation`, `pinned`, `submitted_at`, `superseded_at`, `contribution_domain_id`), indexed on `(source_kind, source_id)` where `superseded_at IS NULL`
- [X] T002 Add `_ZE_PRIORITY_VERSIONS` constant to `apps/ze-api/ze_api/migrate.py` pointing at `core/ze-priority/ze_priority/migrations/`, following the existing pattern for `ze-worldstate`/`ze-skills` (per research.md R5)
- [X] T003 [P] Add the new migration + package row to `CLAUDE.md`'s "Migration ownership" table (`ze-priority | zpri | priority_overrides`) and package dependency graph note

**Checkpoint**: `make migrate` applies `zpri001` cleanly against a fresh `make db-up` database

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, store, and the cross-cutting collision-detector change every user story's write path depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Add `PriorityOverride` dataclass to `core/ze-priority/ze_priority/types.py` per data-model.md (fields: `id`, `source_kind`, `source_id`, `anchor_source_kind`, `anchor_source_id`, `relation: Literal["above","below"]`, `pinned: bool`, `submitted_at`, `superseded_at`, `contribution_domain_id`)
- [X] T005 [P] Add `PriorityOverrideNotFoundError` and `StaleReprioritizationTargetError` to `core/ze-priority/ze_priority/errors.py` (subclassing the existing `ZePriorityError`)
- [X] T006 Implement `PriorityOverrideStore` in `core/ze-priority/ze_priority/store.py` — `create(override) -> PriorityOverride` (supersedes any existing active row for the same `(source_kind, source_id)` in the same transaction, per data-model.md), `get_active() -> list[PriorityOverride]` (excludes superseded rows), `get(id) -> PriorityOverride | None`, `unpin(id) -> PriorityOverride` (raises `PriorityOverrideNotFoundError` if no active row matches)
- [X] T007 [P] Modify `_find_candidates()` in `core/ze-collision/ze_collision/detect.py` — narrow the skip condition from `existing.source_function == new.source_function` to also require `existing.provenance == new.provenance` before skipping (research.md R1); this requires adding `provenance: Provenance` to `CollisionCandidate` in `core/ze-collision/ze_collision/types.py` and populating it in `submit_and_detect_collisions()` (`detect.py`) from `contribution.provenance`
- [X] T008 [P] [Tests] Update `core/ze-collision/tests/test_detect.py` — add a case asserting two same-`source_function`-different-`provenance` candidates ARE compared (not skipped), and that the existing same-`source_function`-same-`provenance` skip (Phase 126's original FR-002/FR-007 case) still holds
- [X] T009 [P] Add `PrioritySnapshotItem`, `PriorityOverrideRequest`, `PriorityOverrideResponse` Pydantic models to `apps/ze-api/ze_api/api/schemas.py` per `contracts/rest-api.md`
- [X] T010 Wire `priority_override_store: PriorityOverrideStore` into `apps/ze-api/ze_api/container.py` (constructed alongside the existing `priority_view = PriorityView(...)` at line ~627) and add a `get_priority_override_store` dependency in `apps/ze-api/ze_api/api/dependencies.py`
- [X] T011 [P] [Tests] Unit tests for `PriorityOverrideStore` in `core/ze-priority/tests/test_store.py` (mock asyncpg pool with `AsyncMock`) — covers create/supersede/get_active/unpin/not-found

**Checkpoint**: Store, types, and the narrowed collision skip-rule are in place and unit-tested; no user-facing behavior yet

---

## Phase 3: User Story 1 - Seeing what Ze currently thinks matters most (Priority: P1) 🎯 MVP

**Goal**: A snapshot view showing `PriorityView`'s current ranked list — loops, stuck/near-gate goals, non-stale hypotheses — each labeled with source and rank.

**Independent Test**: Seed a drifting loop, a stuck goal, and a recent hypothesis; open the snapshot view; assert all three appear labeled with source and rank matching `PriorityView.rank()`.

### Tests for User Story 1

- [X] T012 [P] [US1] Contract test for `GET /api/v0/priority/snapshot` in `apps/ze-api/tests/api/test_priority_routes.py` — asserts response shape matches `contracts/rest-api.md`'s `PrioritySnapshotItem[]`, and empty list (not error) when all three sources are empty (Acceptance Scenario 2)
- [X] T013 [P] [US1] Unit tests for the ranking-merge pure function in `core/ze-priority/tests/test_merge.py` — with no active overrides, merged output equals `PriorityView.rank()`'s unmodified order and `overridden_from_computed=False` for every item

### Implementation for User Story 1

- [X] T014 [US1] Implement the ranking-merge function in `core/ze-priority/ze_priority/merge.py` per data-model.md "Ranking merge" — `merge(ranking: PriorityRanking, overrides: list[PriorityOverride], now: datetime) -> list[MergedPriorityItem]` (with no active overrides, this is a pass-through producing `overridden_from_computed=False` for every item; decay-weighted repositioning is added in US2, T023)
- [X] T015 [US1] Implement `GET /api/v0/priority/snapshot` in new `apps/ze-api/ze_api/api/routes/priority.py`, delegating to a new `ze_priority.rest.get_snapshot(priority_view, override_store)` module function, following the `collisions.py` route pattern (response_model, operation_id, summary, description per Constitution IV)
- [X] T016 [US1] Register the new `priority` router in `apps/ze-api/ze_api/api/app.py` (or wherever routers are included, matching how `loops`/`collisions` routers are registered)
- [X] T017 [P] [US1] Create `apps/ze-web/src/entities/priority-item/api/usePrioritySnapshotQuery.ts` — React Query hook over the generated `@ze/client` `getPrioritySnapshot()` SDK method (regenerate `@ze/client` from the updated OpenAPI spec first)
- [X] T018 [P] [US1] Create `apps/ze-web/src/entities/priority-item/index.ts` exporting the query hook and `PrioritySnapshotItem` type
- [X] T019 [US1] Create `apps/ze-web/src/widgets/priority-snapshot/ui/PrioritySnapshot.tsx` — read-only ranked list (source badge + title + rank), empty state, consuming `usePrioritySnapshotQuery` (drag interaction added in US2, T028)
- [X] T020 [US1] Add a route/nav entry for the new snapshot view in `apps/ze-web/src/app/router/routes.ts` + `shared/config/nav-routes.ts`

**Checkpoint**: Opening the snapshot view shows the three seeded items in `PriorityView.rank()`'s order; empty state works. Fully functional and demoable independent of US2/US3.

---

## Phase 4: User Story 2 - Reordering priorities by dragging (Priority: P1)

**Goal**: Dragging an item to a new position submits a user-stated Contribution and holds the item at the requested position (decaying by default, durable when pinned).

**Independent Test**: Open the snapshot view with three ranked items; drag the third above the first; assert a Contribution is submitted referencing the item and requested order, and the next view-open shows the item at the requested position.

### Tests for User Story 2

- [X] T021 [P] [US2] Contract test for `POST /api/v0/priority/override` and `POST /api/v0/priority/override/{id}/unpin` in `apps/ze-api/tests/api/test_priority_routes.py` — covers success, 404 on stale/nonexistent target, and the FR-015 error-response shape
- [X] T022 [P] [US2] Unit tests for `submit_reprioritization()` in `core/ze-priority/tests/test_service.py` — asserts both the user-override Contribution (`EXECUTIVE`/`PROMPT_SUPPLIED`) and companion contribution (`EXECUTIVE`/`SYNTHESIZED`) are submitted via `submit_and_detect_collisions`, both carrying `entity_ids=[source_id]` (research.md R4); asserts FR-012 supersession (second call for the same item sets `superseded_at` on the first row); asserts FR-011 (submitting against a target no longer present in any `PriorityView` source list raises `StaleReprioritizationTargetError`)
- [X] T023 [P] [US2] Extend `test_merge.py` (`core/ze-priority/tests/test_merge.py`) — decaying override at full weight fully repositions the item adjacent to its anchor (Acceptance Scenario 2, `computed_rank` unchanged); weight linearly interpolated at 24h into the 48h window (R6); weight `0` at/after 48h reverts to unmodified position (Acceptance Scenario 3); pinned override holds full weight regardless of elapsed time (Acceptance Scenario 4); stale target (FR-011) is excluded from the merge entirely; two contradicting overrides resolve by most-recent-`submitted_at`-wins (FR-014, research.md R7)

### Implementation for User Story 2

- [X] T024 [US2] Implement `override_to_contribution()` and `synthesized_claim_contribution()` in new `core/ze-priority/ze_priority/contribution.py`, mirroring `ze_worldstate/contribution.py`'s structure, per data-model.md's "Reprioritization Contribution pair" table
- [X] T025 [US2] Implement `submit_reprioritization(request, *, priority_view, override_store, collision_store, nli_client) -> PriorityOverride` in `core/ze-priority/ze_priority/service.py` — resolves current `PriorityView` state to validate the target and anchor still exist (FR-011, raises `StaleReprioritizationTargetError` otherwise), builds both contributions (T024), submits each via `ze_collision.detect.submit_and_detect_collisions`, persists the resulting `PriorityOverride` via `PriorityOverrideStore.create` (T006)
- [X] T026 [US2] Extend `merge.py` (T014) with the decay-weight calculation (R6: linear from 1.0 at `submitted_at` to 0.0 at `submitted_at + 48h`, pinned = constant 1.0) and cross-item conflict resolution (R7: apply active overrides in ascending `submitted_at` order)
- [X] T027 [US2] Implement `POST /api/v0/priority/override` and `POST /api/v0/priority/override/{id}/unpin` in `apps/ze-api/ze_api/api/routes/priority.py` (T015), delegating to `submit_reprioritization` (T025) and `PriorityOverrideStore.unpin` (T006); map `StaleReprioritizationTargetError` → 404, `PriorityOverrideNotFoundError` → 404
- [X] T028 [US2] Add `@dnd-kit/core` + `@dnd-kit/sortable` to `apps/ze-web/package.json` (research.md R9) and wire drag-and-drop into `PrioritySnapshot.tsx` (T019) — on drop, compute the anchor item + `relation` from the drop position and call the new mutation (T029); on submission failure, revert the drag and show an inline error (FR-015)
- [X] T029 [P] [US2] Create `apps/ze-web/src/entities/priority-item/api/useReprioritizeMutation.ts` — React Query mutation over the generated `submitPriorityOverride()`/`unpinPriorityOverride()` SDK methods, invalidating the snapshot query on success
- [X] T030 [US2] Add the in-view disagreement indicator (FR-010, R2) to `PrioritySnapshot.tsx` — render a subtle badge when `overridden_from_computed=true` on a row
- [X] T031 [US2] Add a pin/unpin toggle control to `PrioritySnapshot.tsx`, distinct from the drag gesture itself (FR-009's "distinct action" requirement)

**Checkpoint**: Dragging reorders, persists, decays, pins, and surfaces disagreement — independently testable and demoable alongside US1.

---

## Phase 5: User Story 3 - Reordering priorities in conversation (Priority: P2)

**Goal**: Telling Ze in chat to reprioritize an item has the same effect as dragging it, with disambiguation and a confirmation gate.

**Independent Test**: With the same three items seeded as US1, tell Ze in conversation to deprioritize the item currently ranked first; assert an equivalent Contribution is submitted and the next snapshot view reflects it.

### Tests for User Story 3

- [X] T032 [P] [US3] Unit tests for `reprioritize_item`'s disambiguation logic in `core/ze-priority/tests/test_tools.py` — exact/near-unique title match proceeds; zero matches and multiple close matches both return a clarification request without calling `submit_reprioritization` (Acceptance Scenario 2)
- [X] T033 [P] [US3] Integration test in `apps/ze-api/tests/` (or wherever agentic-loop/confirmation tests live) asserting `reprioritize_item`'s capability mode routes the graph through `draft_response → await_confirmation` and that the Contribution is submitted only after `EXECUTE`-resume (FR-007)

### Implementation for User Story 3

- [X] T034 [US3] Implement `reprioritize_item` tool in new `core/ze-priority/ze_priority/tools.py` per `contracts/tool-contract.md` — embedding-similarity disambiguation against the current `PriorityView` snapshot titles (reusing `ze_core/embeddings.py`'s singleton per research.md R8), translating `requested_relation`/`pin` into the anchor-relative `PriorityOverrideRequest` shape, calling `submit_reprioritization` (T025) on confirmed execution
- [X] T035 [US3] Set `Mode.CONFIRM` capability for `reprioritize_item` in the relevant capability config so `capability_check` routes it through the existing `await_confirmation` gate (no new confirmation primitive, FR-007)
- [X] T036 [US3] Register `reprioritize_item` in the appropriate agent's tool list and add its module path to the relevant `agent_module_paths()`/bootstrap wiring so `@tool` registration fires at startup
- [X] T037 [US3] Wire the tool's failure path (FR-015) so a failed `submit_reprioritization` call after confirmation surfaces a clear "could not be applied" message back through the agent's response, not a silent success

**Checkpoint**: All three user stories independently functional; conversational path produces the same durable effect as dragging.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T038 [P] Run `make lint` and `make format` across `ze-priority`, `ze-collision`, `ze-api`, `ze-web`
- [X] T039 [P] Run `make test-priority`, `make test-collision`, `make test` (ze-api), `make test-web` — all green (Constitution V)
- [X] T040 Run through `quickstart.md`'s three scenarios end-to-end against `make dev-full`, including the collision-log verification step
- [X] T041 Update spec.md's `Status` field to `Done` in the same commit as this implementation (Constitution I)
- [X] T042 Add a row for phase 127 to the "Phase status" table in `CLAUDE.md` and to `specs/README.md`'s index (Constitution / Development Workflow "Definition of Done")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational only — independently testable/demoable as an MVP
- **US2 (Phase 4)**: Depends on Foundational; reuses US1's `PrioritySnapshot.tsx`/`priority.py`/`priority-item` entity (extends rather than duplicates them) — not a hard blocking dependency on US1 being *finished*, but touches the same files, so sequencing US1 → US2 avoids merge conflicts
- **US3 (Phase 5)**: Depends on Foundational and on `submit_reprioritization` (T025, built in US2) — genuinely depends on US2's service layer, not just file-sharing
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### Parallel Opportunities

- T001/T003 in Setup can run in parallel with each other
- T004/T005/T007/T008/T009/T011 in Foundational can run in parallel (different files)
- T012/T013 (US1 tests) in parallel; T017/T018 (US1 frontend entity files) in parallel
- T021/T022/T023 (US2 tests) in parallel
- T032/T033 (US3 tests) in parallel

---

## Parallel Example: Foundational Phase

```bash
Task: "Add PriorityOverride dataclass to core/ze-priority/ze_priority/types.py"
Task: "Add PriorityOverrideNotFoundError/StaleReprioritizationTargetError to core/ze-priority/ze_priority/errors.py"
Task: "Modify _find_candidates() skip rule in core/ze-collision/ze_collision/detect.py"
Task: "Add Pydantic schemas to apps/ze-api/ze_api/api/schemas.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 — snapshot view, read-only
4. **STOP and VALIDATE**: Open the view against seeded data; confirm order matches `PriorityView.rank()` and the empty state works
5. Demo: "here's what Ze currently thinks matters most"

### Incremental Delivery

1. Setup + Foundational → migration applied, store/types/collision-rule ready
2. US1 → snapshot view demoable (MVP)
3. US2 → drag reorder, decay, pin — demoable alongside US1
4. US3 → conversational path, reusing US2's service layer
5. Polish → lint/tests/quickstart/spec status green across the board

### Notes

- [P] tasks touch different files with no unmet dependencies
- Constitution V makes the test tasks non-optional here — do not skip them
- US2 and US3 both converge on `submit_reprioritization` (T025) per FR-004's "same validated write path" requirement — do not fork a second write path for the conversational tool
