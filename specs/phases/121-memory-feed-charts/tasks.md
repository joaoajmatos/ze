---

description: "Task list template for feature implementation"
---

# Tasks: Memory Feed Charts

**Input**: Design documents from `/specs/phases/121-memory-feed-charts/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — constitution Principle V (Test Discipline) is non-negotiable for this repo.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Path Conventions

`core/ze-memory` (backend), `apps/ze-api` (schema), `packages/ze-client` (generated types), `apps/ze-web/src/pages/brain-memory` (frontend) — per `plan.md`'s Project Structure.

---

## Phase 1: Setup

No new dependencies or scaffolding — reuses spec 118's `packages/ze-ui` chart components.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fix the as-of wiring gap both stories' correctness depends on (FR-003 spans User Story 1 and User Story 2 — both new charts must reflect the page's existing time-travel state, which the underlying query currently ignores).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T001 In `apps/ze-web/src/pages/brain-memory/ui/BrainMemoryPage.tsx`, change `useMemoryActivityQuery(earliest, earliest ? now : undefined)` to pass `asOfDate ?? now` as the second argument, so the query's `end` reflects the page's time-travel state (research.md R4)
- [x] T002 [P] Test: `useMemoryActivityQuery` receives `asOfDate` (not live `now`) as its `end` argument when the page is scrubbed to a past date, in `apps/ze-web/src/pages/brain-memory/ui/BrainMemoryPage.test.tsx` (new file, depends on T001)

**Checkpoint**: Foundation ready — both new charts can now be built on a query that correctly respects as-of state.

---

## Phase 3: User Story 1 - Seeing how memory has grown over time (Priority: P1) 🎯 MVP

**Goal**: A chart shows memory volume (facts + episodes) accumulated/recorded over time on the Memory page.

**Independent Test**: Load the Memory page for a user with activity spread across multiple weeks; confirm a chart shows that activity over time, distinct from the scrubber strip and the feed list.

### Implementation for User Story 1

- [x] T003 [US1] In `BrainMemoryPage.tsx`, render a `LineChart`/`BarChart` of memory volume over time, mapping the existing `activity.days` (`MemoryActivityDay[]`, already fetched for the `TimelineScrubber`) to `ChartPoint[]` via `{x: date, y: count}` (data-model.md — uses `count`, no backend change needed for this story alone)
- [x] T004 [P] [US1] Test: the growth chart renders for multi-week activity data and for a 1–2-day new-user case, in `BrainMemoryPage.test.tsx` (depends on T003)
- [x] T005 [US1] Manual validation: `quickstart.md` §2 (depends on T004)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Understanding what kind of memory dominates (Priority: P2)

**Goal**: A chart shows the proportion of facts vs episodes.

**Independent Test**: Load the Memory page with a mix of facts and episodes; confirm a chart shows their relative proportion.

### Implementation for User Story 2

- [x] T006 [US2] In `core/ze-memory/ze_memory/admin.py`'s `get_memory_activity` (~line 185), change the inner `UNION ALL` to label each half with a `source` column (`'fact'`/`'episode'`), `GROUP BY day, source` instead of collapsing immediately, then reshape the rows in Python into `{date, count: fact_count + episode_count, fact_count, episode_count}` per day (contracts/memory-activity-split.md)
- [x] T007 [P] [US2] Add `fact_count: int` and `episode_count: int` to `MemoryActivityDay` in `apps/ze-api/ze_api/api/schemas.py:859`
- [x] T008 [P] [US2] Test: `get_memory_activity`'s per-day `fact_count + episode_count` sums to `count`, in `core/ze-memory/tests/` (depends on T006)
- [x] T009 [US2] Regenerate `packages/ze-client/src/generated/types.gen.ts` via `bun run scripts/codegen.ts` (depends on T006, T007)
- [x] T010 [US2] In `BrainMemoryPage.tsx`, render a `PieChart` summing `fact_count`/`episode_count` across the currently-loaded `activity.days` (depends on T009, T001)
- [x] T011 [P] [US2] Test: composition chart shows the facts-vs-episodes proportion, and renders a sensible single-category state for a facts-only (or episodes-only) account, in `BrainMemoryPage.test.tsx` (depends on T010)
- [x] T012 [US2] Manual validation: `quickstart.md` §3 (depends on T011)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T013 [P] Verify edge cases per `quickstart.md` §4: new account with minimal data, single-type-only data, narrow viewport
- [x] T014 Update `spec.md`'s Status header to `Implemented` and the `specs/README.md` index row for `121-memory-feed-charts`, in the same commit as the implementation
- [x] T015 Run `make lint`, `make test-memory`, and `make test-web`; all must pass clean

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: BLOCKS both User Story 1 and User Story 2 — the as-of wiring fix (T001) is a shared correctness prerequisite (FR-003).
- **User Story 1 (Phase 3)**: Depends only on Foundational — no backend change needed, `count` already exists.
- **User Story 2 (Phase 4)**: Depends only on Foundational — independent of User Story 1's chart, adds its own backend field + chart.
- **Polish (Phase 5)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- T006 and T007 (US2 backend: query change and schema field) touch different files and can proceed in parallel, converging at T009's codegen step.
- User Story 1 and User Story 2 can be worked on in parallel once Phase 2 is done — US1 needs no backend work at all.

---

## Parallel Example: User Story 2

```bash
Task: "Change get_memory_activity's query to group by (day, source) in core/ze-memory/ze_memory/admin.py"
Task: "Add fact_count/episode_count to MemoryActivityDay in apps/ze-api/ze_api/api/schemas.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2 (Foundational) — fix the as-of wiring gap.
2. Complete Phase 3 (User Story 1) — growth chart, no backend change required.
3. **STOP and VALIDATE**: `quickstart.md` §2.

### Incremental Delivery

1. Foundational → as-of consistency fixed for whatever charts land on top of it.
2. User Story 1 → validate independently → growth chart ships.
3. User Story 2 → validate independently → composition chart ships, backend split lands.

---

## Notes

- [P] tasks = different files, no dependencies.
- Commit after each task or logical group.
- T001 (Foundational) fixes a real pre-existing bug (the scrubber's own density strip has quietly always shown live data) — call this out in the PR description, not just the new charts.
