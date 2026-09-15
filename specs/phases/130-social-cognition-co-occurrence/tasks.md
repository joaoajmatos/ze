---

description: "Task list for Phase 130: Social Cognition Co-Occurrence"
---

# Tasks: Social Cognition Co-Occurrence

**Input**: Design documents from `/specs/phases/130-social-cognition-co-occurrence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/,
quickstart.md (all present)

**Tests**: Included — Constitution V (Test Discipline) is non-negotiable for
this repo; every task below that adds behavior has a paired test task.

**Organization**: Tasks are grouped by user story (spec.md P1/P2/P3) to enable
independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every task

## Path Conventions

Backend-only, existing monorepo layout — no new top-level directory. Touched
packages: `core/cognition/ze-correlation`, `packages/ze-sdk`,
`plugins/ze-personal`, `apps/ze-api`.

---

## Phase 1: Setup

**Purpose**: Scaffolding the new subpackage and SDK dependency before any
behavior is written.

- [X] T001 Create `plugins/ze-personal/ze_personal/social/__init__.py` (empty
      package init, new `social/` subpackage per plan.md Project Structure)
- [X] T002 Add `"ze-correlation"` to `packages/ze-sdk/pyproject.toml`
      `dependencies` and `[tool.uv.sources]` (mirrors the existing
      `ze-memory`/`ze-automation` entries), then run `uv sync` to relock

**Checkpoint**: Package skeleton exists; `ze-sdk` can resolve `ze-correlation`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, store methods, and the SDK re-export every user story's
job/tools code depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Write migration
      `core/cognition/ze-correlation/ze_correlation/migrations/versions/zcor003_hypothesis_confirmation.py`
      — raw SQL `ALTER TABLE correlation_hypothesis ADD COLUMN IF NOT EXISTS
      confirmed BOOLEAN NOT NULL DEFAULT false, ADD COLUMN IF NOT EXISTS
      promoted_at TIMESTAMPTZ NULL` (data-model.md Schema Change), on the
      existing `zcor` chain, `depends_on` the prior `zcor002` revision
- [X] T004 Add `confirm(self, id: UUID) -> Hypothesis`,
      `mark_promoted(self, id: UUID) -> Hypothesis`, and
      `list_by_entities(self, entity_ids: list[UUID]) -> list[Hypothesis]` to
      `PostgresHypothesisStore` in
      `core/cognition/ze-correlation/ze_correlation/store.py` (contracts/social-cooccurrence-contract.md
      `HypothesisStore` Protocol)
- [X] T005 [P] Write tests for T004 in
      `core/cognition/ze-correlation/tests/test_store.py` (extend existing
      file) — `confirm()` flips the flag, `mark_promoted()` sets `promoted_at`,
      `list_by_entities()` returns only hypotheses whose `entities` intersects
      the given ids
- [X] T006 [P] Create `packages/ze-sdk/ze_sdk/correlation.py` re-exporting
      `Hypothesis`, `EvidenceRef`, and a `HypothesisStore` Protocol (matching
      `PostgresHypothesisStore`'s public methods including T004's additions),
      mirroring `ze_sdk/memory.py`'s re-export shape
- [X] T007 [P] Write a smoke test in `packages/ze-sdk/tests/test_correlation.py`
      asserting `ze_sdk.correlation.Hypothesis` is the same class as
      `ze_correlation.types.Hypothesis` (re-export correctness, matching any
      existing `ze_sdk/tests/test_memory.py`-style check)
- [X] T008 [P] Create `plugins/ze-personal/ze_personal/social/types.py` with
      `CoOccurrenceCandidate` and `CoOccurrenceEvidenceEvent` dataclasses
      (data-model.md — job-internal, never persisted directly)
- [X] T009 Wire a `hypothesis_store` (via `ze_sdk.correlation`) into
      `apps/ze-api/ze_api/container.py`'s dependency map if not already
      present under that name (the existing `ze_correlation` engine wiring
      already constructs a `PostgresHypothesisStore` — confirm/reuse that
      instance rather than constructing a second one)

**Checkpoint**: Schema, store surface, and SDK access exist. User story work
can begin.

---

## Phase 3: User Story 1 - Ze notices who is on a project (Priority: P1) 🎯 MVP

**Goal**: From recent (30-day) communication evidence, form and persist a
hedged `INFERENCE` hypothesis linking a person to a project, weighted by
`SOURCE_WEIGHTS`, without writing any identity edge. A conversational ask
("who seems to be on X?") returns that hedged belief with cited evidence.

**Independent Test**: Feed fixture evidence (a reply-thread email + a calendar
meeting, both inside 30 days, both real participation not just CC) for one
known person and one known project; run the job; assert a `Hypothesis`
(`claim_kind=INFERENCE`) exists with those two evidence items and no
`WORKS_ON` edge exists in the graph; call `who_is_on_project` and assert the
hedged answer names the person and cites at least one evidence item.

### Tests for User Story 1

- [X] T010 [P] [US1] Write `plugins/ze-personal/tests/social/test_scoring.py`
      covering: `SOURCE_WEIGHTS` lookup by `source_type`/`is_reply_or_attendee`
      (reply/attendee → conversation or its source's normal tier; CC-only →
      research-tier per FR-004); evidence outside the 30-day window (via
      `ze_proactive.staleness.is_stale()`) is excluded from scoring (FR-003)
- [X] T011 [P] [US1] Write
      `plugins/ze-personal/tests/jobs/test_social_cooccurrence.py::test_forms_hypothesis_from_evidence`
      — given fixture `CoOccurrenceEvidenceEvent`s for one person/project pair,
      the job creates a `Hypothesis` with `claim_kind=INFERENCE`,
      `source_function=SourceFunction.REFLECTION` on the submitted
      `Contribution`, evidence ids matching the fixture, and does not call
      `graph_store.upsert_relationship` (mock `HypothesisStore`, `GraphStore`,
      `CollisionLogStore`, `NLIClient` per Constitution V)
- [X] T012 [P] [US1] Write
      `plugins/ze-personal/tests/social/test_tools.py::test_who_is_on_project_hedged`
      — with one unconfirmed hypothesis and no promoted edge, the tool returns
      it under `hedged_candidates` (not `confirmed_members`), with an evidence
      summary; with no hypothesis and no edge, both lists are empty

### Implementation for User Story 1

- [X] T013 [US1] Implement evidence weighting in
      `plugins/ze-personal/ze_personal/social/scoring.py`:
      `score_evidence(events: list[CoOccurrenceEvidenceEvent]) -> float` using
      `ze_personal.contacts.types.SOURCE_WEIGHTS` verbatim (FR-004), filtering
      out anything `ze_proactive.staleness.is_stale(event.occurred_at, 30)`
      (FR-003) (depends on T008, T010 failing first)
- [X] T014 [US1] Implement
      `plugins/ze-personal/ze_personal/jobs/social_cooccurrence.py`:
      `SocialCooccurrenceJob` (`@proactive_job`, `job_id =
      "social_cooccurrence"`) — `run()` scans known person/project and
      person/person pairs with fresh evidence in the graph neighbourhood,
      builds `CoOccurrenceCandidate`s, calls `scoring.score_evidence()`,
      creates or updates the pair's `Hypothesis` via
      `ze_sdk.contribution.submit_and_detect_collisions` with the hypothesis
      `Contribution` shape from contracts/social-cooccurrence-contract.md
      (`source_function=SourceFunction.REFLECTION`, `claim_kind=INFERENCE`)
      (depends on T013)
- [X] T015 [US1] Implement
      `plugins/ze-personal/ze_personal/social/tools.py::who_is_on_project` —
      queries `GraphStore` for confirmed, in-window `WORKS_ON` edges and
      `HypothesisStore.list_by_entities()` for unconfirmed, unpromoted
      hypotheses on the same project entity; returns `WhoIsOnProjectResult`
      keeping `confirmed_members`/`hedged_candidates` separate per
      contracts/social-cooccurrence-contract.md (depends on T004, T006)
- [X] T016 [US1] Register the job and tools module in
      `plugins/ze-personal/ze_personal/plugin.py`: add
      `"ze_personal.social.tools"` to `agent_module_paths()`, add
      `self.social_cooccurrence` to `jobs()`, construct
      `SocialCooccurrenceJob` in `__init__`/wherever other jobs are
      constructed (mirror `ContactReview`/`InsightEngine`'s existing
      construction site)

**Checkpoint**: User Story 1 is fully functional and independently testable —
hypotheses form and hedge correctly; nothing is promoted yet.

---

## Phase 4: User Story 2 - A corroborated pattern becomes a real graph edge (Priority: P1)

**Goal**: Once a hypothesis is corroborated (2 independent events across 2
distinct days, research.md Decision 3) or the user explicitly confirms, write
a real `WORKS_ON`/`COLLABORATES_WITH` identity edge through the contribution
seam.

**Independent Test**: Drive a hypothesis to 2 distinct-day, distinct-event
evidence entries; run the job; assert a `WORKS_ON` edge now exists in the
graph and `Hypothesis.promoted_at` is set. Separately, call
`confirm_project_membership` on a fresh, uncorroborated hypothesis and assert
the same edge appears immediately. A second hypothesis with only 1 event never
gets promoted by the job alone.

### Tests for User Story 2

- [X] T017 [P] [US2] Extend `test_scoring.py` (T010) with
      `test_corroboration_gate` — passes only with ≥2 events with distinct
      `event_id`s spanning ≥2 distinct `occurred_at` calendar days inside the
      window; a single event, or two events on the same day, or two events
      from the same `event_id`, all fail the gate (research.md Decision 3)
- [X] T018 [P] [US2] Write
      `plugins/ze-personal/tests/graph/test_memory_hooks.py::test_write_relationship_edge_via_seam`
      — asserts the new function submits a `Contribution(claim_kind=IDENTITY,
      source_function=SourceFunction.SOCIAL_COGNITION, ...)` via
      `submit_and_detect_collisions` and only then calls
      `graph_store.upsert_relationship`; a `Contribution` with the wrong
      `source_function` (e.g. `REFLECTION`) is rejected by the seam before any
      graph write (regression test for research.md Decision 1)
- [X] T019 [P] [US2] Extend `test_social_cooccurrence.py` (T011) with
      `test_promotes_on_corroboration` (gate passes → edge written, `promoted_at`
      set, second run does not re-submit) and
      `test_does_not_promote_below_corroboration` (1 event → hypothesis
      updated, no edge, no seam call for promotion)
- [X] T020 [P] [US2] Write
      `test_tools.py::test_confirm_project_membership` — confirming an
      uncorroborated hypothesis sets `confirmed=true` and promotes
      immediately, reusing the same promotion path as the job (no duplicated
      write logic — assert both call sites hit the same
      `_write_relationship_edge_via_seam` function, e.g. via a shared mock)

### Implementation for User Story 2

- [X] T021 [US2] Implement the corroboration gate in
      `plugins/ze-personal/ze_personal/social/scoring.py`:
      `is_corroborated(events: list[CoOccurrenceEvidenceEvent]) -> bool` per
      research.md Decision 3 (depends on T017 failing first)
- [X] T022 [US2] Implement
      `_write_relationship_edge_via_seam()` in
      `plugins/ze-personal/ze_personal/graph/memory_hooks.py` — reuses the
      entity-upsert logic already in `_write_relationship_edge()` but wraps
      the `graph_store.upsert_relationship()` call as the `write` callback
      inside `ze_sdk.contribution.submit_and_detect_collisions`, building the
      promotion `Contribution` shape from
      contracts/social-cooccurrence-contract.md (depends on T018 failing
      first; does NOT modify the existing `_write_relationship_edge()`, per
      research.md Decision 5)
- [X] T023 [US2] Extend `SocialCooccurrenceJob.run()`
      (`ze_personal/jobs/social_cooccurrence.py`) to call
      `scoring.is_corroborated()` after updating each hypothesis; on pass (and
      `promoted_at` not already set), call `_write_relationship_edge_via_seam()`
      then `hypothesis_store.mark_promoted(hypothesis.id)` (depends on T021,
      T022)
- [X] T024 [US2] Implement
      `plugins/ze-personal/ze_personal/social/tools.py::confirm_project_membership`
      — calls `hypothesis_store.confirm(hypothesis_id)`, then if
      `promoted_at` is unset, calls the same promotion helper T023 uses
      (extract a shared `_promote_hypothesis()` helper in
      `social/scoring.py` or `jobs/social_cooccurrence.py` so both call sites
      share one code path, per T020's assertion) (depends on T022, T023)

**Checkpoint**: User Stories 1 AND 2 both work independently — hypotheses
form, hedge, and now promote correctly on corroboration or confirm.

---

## Phase 5: User Story 3 - Wrong or stale guesses do not become the directory (Priority: P2)

**Goal**: A single CC-heavy broadcast never promotes or surfaces as settled;
an aged-out membership drops from "currently on this project" without closing
the project; an inference already covered by an extracted edge reinforces
`last_contact` instead of duplicating.

**Independent Test**: (a) Feed one CC-only, no-reply broadcast fixture naming
many people and a project; run the job; assert zero `WORKS_ON` edges and zero
entries in `hedged_candidates` presented as settled. (b) Promote a membership,
backdate its `last_contact` past 30 days; assert it's excluded from a
current-membership read while the project entity remains queryable. (c) Feed
evidence for a pair that already has a `WORKS_ON` edge; assert no duplicate
hypothesis/edge is created and `last_contact` is reinforced.

### Tests for User Story 3

- [X] T025 [P] [US3] Extend `test_scoring.py` with
      `test_cc_only_broadcast_never_corroborates` — many people, one event,
      all `is_reply_or_attendee=False` (research-tier weight): each
      individual hypothesis fails both the confidence bar implied by
      research-tier weighting alone and the corroboration gate (single event,
      single day) (SC-003)
- [X] T026 [P] [US3] Extend `test_social_cooccurrence.py` with
      `test_existing_edge_reinforced_not_duplicated` — when
      `CoOccurrenceCandidate.existing_edge_exists=True`, the job calls
      `graph_store.upsert_relationship()` directly (reinforcing
      `last_contact`, reusing the existing `GREATEST()` upsert path) and does
      **not** create/update a `Hypothesis` for that pair (Edge Case in
      spec.md)
- [X] T027 [P] [US3] Write
      `plugins/ze-personal/tests/social/test_priority_exclusion.py` (or add to
      an existing `ze-priority` integration test) asserting
      `RelationshipStalenessSource.list_stale_for_follow_up()` never returns a
      row sourced from an unconfirmed, unpromoted `Hypothesis` — only from
      confirmed `contacts` rows, unchanged from Phase 128 (FR-010, SC-005)
- [X] T028 [P] [US3] Write a `ze-memory` graph-store test (extend existing
      relationship tests) confirming a person whose only promoted edge has
      `last_contact` older than 30 days is excluded from a
      `is_stale(last_contact, 30) is False`-filtered read, while the project
      `Entity` row itself remains fetchable with no `active`/`closed` field
      (SC-004, mirrors Phase 128's existing freshness behavior — this task
      only adds the co-occurrence-specific fixture, not a new mechanism)

### Implementation for User Story 3

- [X] T029 [US3] In `SocialCooccurrenceJob.run()`
      (`ze_personal/jobs/social_cooccurrence.py`), branch on
      `CoOccurrenceCandidate.existing_edge_exists`: when `True`, call
      `graph_store.upsert_relationship()` to reinforce `last_contact` only,
      skipping hypothesis creation/update entirely for that pair (depends on
      T026 failing first)
- [X] T030 [US3] Verify (and add a code comment recording the check, not new
      logic) that `apps/ze-api/ze_api/container.py`'s
      `RelationshipStalenessSource` wiring for `PriorityView` still points
      only at `PersonStore.list_stale_for_follow_up()` — confirm no wiring
      path routes `SocialCooccurrenceJob`'s hypotheses into
      `ze_priority`/`push_log` budget consumption (depends on T027 failing
      first; this is a negative-space verification, not new code — FR-010)

**Checkpoint**: All three user stories are independently functional. Wrong
guesses stay hedged-or-nothing; stale memberships fall out of view without a
lifecycle field; extraction and inference never double-write the same edge.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide hygiene and closing the spec-first loop.

- [ ] T031 [P] Run `specs/phases/130-social-cognition-co-occurrence/quickstart.md`
      end-to-end against a local `make dev` + seeded fixtures; fix any
      drift found between the doc and actual behavior
      **NOT DONE in this implementation pass** — no live Postgres/`make dev`
      instance in this session. All logic validated via unit tests (`make
      test-correlation`, `test-sdk`, `test-memory`, `test-personal`, all
      green) with mocked stores per Constitution V. Run this manually before
      considering the phase fully closed out.
- [X] T032 [P] Add a `specs/README.md` index row for phase 130 (mirroring the
      128/129 rows already present)
- [X] T033 Run `make lint` and fix any violations across
      `core/cognition/ze-correlation`, `packages/ze-sdk`,
      `plugins/ze-personal`
- [X] T034 Run `make test-ze-correlation`, `make test-ze-sdk`,
      `make test-ze-personal`, `make test-ze-api` — all green
      (Constitution V, Definition of Done)
- [X] T035 Flip `specs/phases/130-social-cognition-co-occurrence/spec.md`
      **Status** from `Planned` to `Implemented` in the same commit as the
      implementation (Constitution I)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational; its promotion path
  (`_write_relationship_edge_via_seam`) is independent of US1's tools/job
  code but its job integration (T023) extends the same
  `SocialCooccurrenceJob.run()` US1 created (T014) — implement US1 first in
  practice, though US2's own tests (T017–T020) can be written in parallel
  with US1
- **User Story 3 (Phase 5)**: Depends on Foundational; its reinforcement
  branch (T029) and priority-exclusion check (T030) touch the same job file
  as US1/US2 — implement after US2 to avoid merge churn, though its tests
  (T025–T028) have no code dependency and can be written any time after
  Foundational
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Within Each User Story

- Tests before implementation (write, confirm failing, then implement)
- `scoring.py` changes before `jobs/social_cooccurrence.py` changes that call
  them
- `graph/memory_hooks.py` changes before `jobs/social_cooccurrence.py`'s
  promotion branch that calls them
- Story complete before moving to the next priority

### Parallel Opportunities

- T005, T006/T007, T008 (Phase 2) touch three different files — parallelizable
- T010, T011, T012 (US1 tests) touch three different test files — parallelizable
- T017, T018, T019, T020 (US2 tests) touch four different test files —
  parallelizable
- T025, T026, T027, T028 (US3 tests) touch four different test files —
  parallelizable
- T031, T032 (Polish) are independent — parallelizable

---

## Parallel Example: User Story 1

```bash
# Launch all three US1 test files together:
Task: "Write plugins/ze-personal/tests/social/test_scoring.py (T010)"
Task: "Write plugins/ze-personal/tests/jobs/test_social_cooccurrence.py::test_forms_hypothesis_from_evidence (T011)"
Task: "Write plugins/ze-personal/tests/social/test_tools.py::test_who_is_on_project_hedged (T012)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (schema, store methods, SDK re-export)
3. Complete Phase 3: User Story 1 — hedged hypotheses form and surface
4. **STOP and VALIDATE**: quickstart.md §1 passes; no identity edge exists yet
5. This alone is a safe, demoable increment — Ze can now say "seems to be on"
   without any promotion risk

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → hedged inference only (MVP)
3. User Story 2 → corroboration/confirm promotes to a real edge
4. User Story 3 → safety nets (CC-only never promotes, no dedup with
   extraction, no budget spend) — validated last but its guard logic
   (research-tier weighting, existing-edge check) is exercised by every
   fixture from US1 onward, so regressions surface early even before its own
   tests are written
5. Polish → lint, full test suite, spec status flip, README index row

### Parallel Team Strategy

1. One person: Foundational (Phase 2) — short, blocking
2. Once done: one person on US1 (scoring + job + tool), one person on US2's
   seam-write helper (T022, independent of US1's tool code) — sequence the
   job-integration tasks (T023, T029) once both land, since they edit the same
   file
3. US3's tests can be written by a third person any time after Foundational,
   implementation slotted in after US2 lands

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Verify tests fail before implementing (Constitution V)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- `SocialCooccurrenceJob.run()` and `graph/memory_hooks.py` are each touched
  by more than one story — sequence those specific tasks (noted above) even
  though stories are otherwise independent
