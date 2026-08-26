---

description: "Task list for Contribution Collision Detection (phase 126)"
---

# Tasks: Contribution Collision Detection

**Input**: Design documents from `/specs/phases/126-contribution-collision-detection/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/collisions-api.md, quickstart.md

**Tests**: Included — constitution Principle V ("Test Discipline (NON-NEGOTIABLE)") mandates
tests for every feature; not optional for this repo.

**Organization**: Tasks are grouped by user story (US1 P1, US2 P1, US3 P2, per spec.md) to enable
independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single monorepo, multi-package: new core package at `core/ze-collision/`, plus small edits across
five existing packages at their established paths (per plan.md's Project Structure).

---

## Phase 1: Setup

**Purpose**: Scaffold the new `ze-collision` package so foundational work has somewhere to land.

- [X] T001 Create `core/ze-collision/pyproject.toml` (package name `ze-collision`, deps on
      `ze-agents`, `ze-plugin`, `ze-logging`; workspace already globs `core/*`, no root
      `pyproject.toml` edit needed — verified `[tool.uv.workspace] members = ["core/*", ...]`)
- [X] T002 Create `core/ze-collision/ze_collision/__init__.py` and `core/ze-collision/tests/__init__.py`
- [X] T003 [P] Add `test-collision` target to `Makefile` (mirror `test-worldstate`/`test-skills`
      targets at lines ~315/321) and list it in the `test-all` aggregate

**Checkpoint**: Package importable, `make test-collision` runs (with zero tests, passes trivially).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, store, and the `Contribution` extension every user story depends on.
**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Add `content: str | None = None` and `entity_ids: list[UUID] = field(default_factory=list)`
      fields to `Contribution` in `core/ze-plugin/ze_plugin/contribution.py` (data-model.md
      "Modified: Contribution") — additive only, `validate_and_submit`'s own body is untouched
- [X] T005 [P] Update `core/ze-plugin/tests/test_contribution.py` to cover the two new optional
      fields (default values, and that `validate_and_submit`'s behavior is unaffected by their
      presence/absence)
- [X] T006 [P] Create `CollisionLogEntry` dataclass in `core/ze-collision/ze_collision/types.py`
      (data-model.md "New: CollisionLogEntry") plus the internal `CollisionCandidate` dataclass
      used by the recency-window scan
- [X] T007 Create migration `core/ze-collision/ze_collision/migrations/versions/zcol001_contribution_collisions.py`
      — raw-SQL Alembic migration for the `contribution_collisions` table and the three indexes
      from data-model.md (`(matched_entity_id, created_at)`,
      `(contribution_a_source_function, contribution_b_source_function, created_at)`,
      `(created_at)`) — depends on T006 for field names
- [X] T008 Register the new chain in `apps/ze-api/ze_api/migrate.py`: add
      `_ZE_COLLISION_VERSIONS = Path(ze_collision.__file__).parent / "migrations" / "versions"`
      alongside the other non-plugin core packages, and add `ze-collision` to
      `apps/ze-api/pyproject.toml` dependencies
- [X] T009 Create `CollisionLogStore` Protocol + `PostgresCollisionLogStore` in
      `core/ze-collision/ze_collision/store.py` (`log()`, `list()` per data-model.md's Store
      section, modeled on `core/ze-proactive/ze_proactive/push_log_store.py`) — depends on T006, T007
- [X] T010 [P] Unit tests for `PostgresCollisionLogStore` in `core/ze-collision/tests/test_store.py`
      (mock asyncpg pool, per constitution Principle V — no real DB)
- [X] T011 Wire `CollisionLogStore` construction and the existing injected `NLIClient` into
      `apps/ze-api/ze_api/container.py` (same pattern as `LoopStore`/`SkillStore` wiring at the
      lines already housing those) — depends on T009

**Checkpoint**: `Contribution` carries the new fields, the collision store exists and is wired
into DI, migrations apply cleanly via `make migrate`. No detection logic yet — nothing observes
collisions until User Story 1.

---

## Phase 3: User Story 1 - A real collision gets logged, not silently absorbed (Priority: P1) 🎯 MVP

**Goal**: Two contributions from different `source_function`s that genuinely conflict about the
same entity get logged, while both writes still succeed normally.

**Independent Test**: Submit a `FACT` from perception linking entity X ("X moved to Berlin"),
then an `INFERENCE` from reflection linking the same X implying the prior location, within the
window. Assert one collision log entry referencing both, and both contributions persisted.

### Tests for User Story 1

- [X] T012 [P] [US1] Unit test in `core/ze-collision/tests/test_detect.py`: conflicting
      cross-function pair sharing an entity produces exactly one `CollisionLogEntry` (mock
      `NLIClient.scores` to return a contradiction score)
- [X] T013 [P] [US1] Unit test in `core/ze-collision/tests/test_detect.py`: a pair from the
      *same* `source_function` never becomes a candidate (FR-002/FR-007 — asserts
      `NLIClient.scores` is never called for such a pair)
- [X] T014 [P] [US1] Unit test in `core/ze-collision/tests/test_detect.py`: `write()`'s return
      value and any exception it raises pass through `submit_and_detect_collisions()` unchanged
      versus calling `validate_and_submit()` directly (contract from contracts/collisions-api.md)

### Implementation for User Story 1

- [X] T015 [US1] Implement the recency-window candidate index (in-process, bounded by
      `_COLLISION_WINDOW_HOURS`) in `core/ze-collision/ze_collision/detect.py`, keyed by entity
      ID and by `target_face`, storing `CollisionCandidate` — depends on T006
- [X] T016 [US1] Implement `submit_and_detect_collisions()` in
      `core/ze-collision/ze_collision/detect.py`: delegates to the unmodified
      `ze_plugin.contribution.validate_and_submit()`, then on success runs the candidate scan
      (entity match, falling back to `target_face` per FR-002) and calls
      `NLIClient.scores([(content_a, content_b)])` for each candidate pair, logging a
      `CollisionLogEntry` via `CollisionLogStore.log()` when contradiction is flagged — depends
      on T009, T015
- [X] T017 [US1] [P] Update `loop_to_contribution()` in `core/ze-worldstate/ze_worldstate/contribution.py`
      to populate `content=loop.title` and accept/pass through `entity_ids`
- [X] T018 [US1] Update the two call sites in `core/ze-worldstate/ze_worldstate/extraction.py`
      (lines ~161, ~294) to call `submit_and_detect_collisions()` instead of
      `validate_and_submit()`, passing `result_id=lambda created: created.id`,
      `producer_kind="open_loop"`, and the already-resolved `entity_ids` — depends on T016, T017
- [X] T019 [US1] [P] Update `signal_to_contribution()` in `core/ze-memory/ze_memory/contribution.py`
      to populate `content=f"{signal.title} {signal.summary}"` and `entity_ids` from
      `signal.entities`
- [X] T020 [US1] Update the call site in `core/ze-memory/ze_memory/retriever.py` (line ~1267) to
      call `submit_and_detect_collisions()` — depends on T016, T019
- [X] T021 [US1] [P] Update the inline `Contribution` construction in
      `core/ze-memory/ze_memory/dream/dream_pass.py` (line ~509) to pass `content=content` (the
      parameter already in scope) and switch the call at line ~516 to
      `submit_and_detect_collisions()`, `producer_kind="dream_artifact"` — depends on T016
- [X] T022 [US1] [P] Update the inline `Contribution` construction in
      `core/ze-correlation/ze_correlation/engine.py` (`_save_hypothesis_via_seam`, line ~240) to
      pass `content=` from the hypothesis's claim text and `entity_ids=` derived from
      `hypothesis.evidence`, and switch the call at line ~252 to
      `submit_and_detect_collisions()`, `producer_kind="hypothesis"` — depends on T016
- [X] T023 [US1] [P] Update `person_source_to_contribution()` in
      `plugins/ze-personal/ze_personal/contacts/contribution.py` to populate `content=` (source
      name/identity text) and `entity_ids=[source person id]` where resolvable
- [X] T024 [US1] Update the two call sites in
      `plugins/ze-personal/ze_personal/contacts/consolidator.py` (lines ~174, ~199) and the two
      in `plugins/ze-personal/ze_personal/graph/memory_hooks.py` (lines ~58, ~81) to call
      `submit_and_detect_collisions()`, `producer_kind="contact"` — depends on T016, T023
- [X] T025 [US1] Run the existing test suites for all five touched packages unchanged
      (`make test-worldstate test-memory test-correlation test-personal`) to confirm FR-001's
      "without altering that path's existing validation, persistence, or rejection behavior"
      holds

**Checkpoint**: User Story 1 fully functional — collisions are detected and logged, source writes
unaffected. This is the MVP.

---

## Phase 4: User Story 2 - Thematic overlap without real conflict is not logged (Priority: P1)

**Goal**: Pairs that merely co-occur (same entity/target_face, compatible or unrelated content)
never produce a log entry.

**Independent Test**: Submit two different-`source_function` contributions on the same entity
with compatible content; assert zero collision log entries.

### Tests for User Story 2

- [X] T026 [P] [US2] Unit test in `core/ze-collision/tests/test_detect.py`: same-entity,
      different-`source_function`, compatible content (mock `NLIClient.scores` returning
      entailment/neutral, not contradiction) → zero log entries
- [X] T027 [P] [US2] Unit test in `core/ze-collision/tests/test_detect.py`: same `target_face`,
      no shared entity, unrelated content → zero log entries (target_face-only match still
      requires the NLI check to fire and fail to detect contradiction)
- [X] T028 [P] [US2] Unit test in `core/ze-collision/tests/test_detect.py`: three contributions
      from three different functions sharing an entity, only one genuinely-conflicting pair →
      exactly one log entry, not three (pairwise, not group-based)

### Implementation for User Story 2

- [X] T029 [US2] Harden the NLI-result interpretation in
      `core/ze-collision/ze_collision/detect.py`'s scoring step so only a genuine
      contradiction-labeled result logs a collision — entailment/neutral scores, or a `None`
      (unscorable) result, must not — depends on T016

**Checkpoint**: User Stories 1 and 2 both hold — real collisions logged, noise filtered out.

---

## Phase 5: User Story 3 - Collision log is queryable for review (Priority: P2)

**Goal**: A maintainer can list logged collisions filtered by entity, `source_function`, or date
range.

**Independent Test**: Log several collisions across different pairs/entities; query filtered by
entity; assert only matching entries return with full review detail.

### Tests for User Story 3

- [X] T030 [P] [US3] Contract test in `core/ze-collision/tests/test_rest.py` for
      `list_collisions()` filtering by `entity_id`, `source_function`, `since`/`until`, and
      `limit` (per contracts/collisions-api.md)
- [X] T031 [P] [US3] Integration test in `apps/ze-api/tests/api/test_collisions.py` for
      `GET /api/v0/collisions` — auth required, query params applied, response shape matches the
      contract's example payload

### Implementation for User Story 3

- [X] T032 [US3] Implement `list_collisions()` in `core/ze-collision/ze_collision/rest.py`
      (entity/source_function/date-range filters over `CollisionLogStore.list()`) — depends on T009
- [X] T033 [US3] Add `CollisionLogEntrySchema` (and `ContributionRefSchema` for the nested
      `contribution_a`/`contribution_b`) to `apps/ze-api/ze_api/api/schemas.py`
- [X] T034 [US3] Create `apps/ze-api/ze_api/api/routes/collisions.py`: `GET /api/v0/collisions`
      with `response_model`, `summary`, `description`, `require_api_key` auth, annotated `Query(...)`
      params — depends on T032, T033
- [X] T035 [US3] Register the new route in the FastAPI app's router assembly (wherever the other
      `/api/v0/` routers — loops, notifications, skills — are included)

**Checkpoint**: All three user stories independently functional; maintainer can answer "has the
arbitration trigger fired" from the log alone (SC-004).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T036 [P] Fault-injection test in `core/ze-collision/tests/test_detect.py`: `NLIClient.scores`
      raises / times out → both writes still succeed, zero log entries, no exception escapes
      `submit_and_detect_collisions()` (SC-003)
- [X] T037 [P] Run `specs/phases/126-contribution-collision-detection/quickstart.md`'s five
      scenarios end-to-end against a local `make dev` + `make db-up` stack
- [X] T038 `make lint && make format` across all six touched packages
- [X] T039 [P] Update `CLAUDE.md`: add `ze-collision` to the repository layout tree, the package
      dependency graph (`ze-collision → ze-agents, ze-plugin, ze-logging core/`), and the
      Migration ownership table (`ze-collision | zcol | contribution_collisions`)
- [X] T040 Update `specs/README.md` index row and this spec's `Status` field (Draft → Implemented)
      in the same commit as the implementation, per constitution Principle I

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — no dependency on US2/US3
- **User Story 2 (Phase 4)**: Depends on Foundational; in practice builds directly on US1's
  `detect.py` (same file, T029 refines T016), so implement after US1 even though both are P1
- **User Story 3 (Phase 5)**: Depends on Foundational (specifically T009's store) — independent
  of US1/US2's detection logic, could be built in parallel with Phase 3/4 by a second engineer,
  but has nothing to query until collisions exist
- **Polish (Phase 6)**: Depends on all three user stories

### Parallel Opportunities

- T004–T006, T010 within Foundational
- T017, T019, T021, T022, T023 (the five `_to_contribution()` helper edits) are independent files
- T012–T014 (US1 tests) in parallel; T026–T028 (US2 tests) in parallel; T030–T031 (US3 tests) in
  parallel
- T036, T037, T039 in Polish

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (User Story 1)
2. **STOP and VALIDATE**: run quickstart.md Scenario 1 — a real collision gets logged, both
   writes intact
3. This alone answers the spec's core question ("has the trigger condition ever fired") even
   before US2/US3 land, though without noise filtering (US2) the log's evidentiary value is
   lower and without a query surface (US3) it can only be inspected via direct DB access

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → collisions detected and logged (MVP)
3. User Story 2 → false positives eliminated, log becomes trustworthy evidence
4. User Story 3 → log becomes reviewable without manual DB queries (SC-004)
5. Polish → hardening, docs, quickstart validation
