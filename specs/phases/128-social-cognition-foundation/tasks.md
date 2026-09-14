---

description: "Task list for Social Cognition Foundation (phase 128)"
---

# Tasks: Social Cognition Foundation

**Input**: Design documents from `specs/phases/128-social-cognition-foundation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included — Constitution Principle V ("Test Discipline") is
NON-NEGOTIABLE for this project; every task group below ships tests before
or alongside its implementation.

**Organization**: Tasks are grouped by user story (US1/US2/US3, matching
spec.md's priorities P1/P2/P2) so each can be implemented and validated
independently, per quickstart.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact, per plan.md's Project Structure section

---

## Phase 1: Setup

No new project/package is created (plan.md's Structure Decision — every
file touched already exists except the two migrations). Nothing to
initialize beyond what Phase 2 does directly.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Graph-schema and vocabulary changes that both US1 and US2
depend on. US3 does **not** depend on this phase (it touches
`core/arbitration/ze-priority`/`plugins/ze-personal`'s briefing job only) and may be
built in parallel with Phase 2/US1/US2 — see Dependencies section.

**⚠️ CRITICAL**: US1 and US2 cannot start until this phase is complete.

- [X] T001 Create migration `core/cognition/ze-memory/ze_memory/migrations/versions/zm019_relationship_last_contact.py` (revision `zm019`, down_revision `zm018`): add `last_contact TIMESTAMPTZ` to `memory_relationships`, backfilled to `created_at` for existing rows (research.md §2/§Summary)
- [X] T002 [P] Add `"project"` to the documented `entity_type` allowed-values comment on `EntityRef.entity_type` and `Entity.entity_type` in `core/cognition/ze-memory/ze_memory/types.py` (contracts/memory-graph-vocabulary.md)
- [X] T003 [P] Add `"project"` to the recognized-type list in the LLM extraction prompt in `core/cognition/ze-memory/ze_memory/extractor.py` (currently defaults unrecognized types to `"concept"` — research.md §1) so generic extraction classifies project mentions correctly
- [X] T004 [P] Add `WORKS_ON` (`# person → project`) and `COLLABORATES_WITH` (`# person ↔ person`) constants to `core/cognition/ze-memory/ze_memory/graph/predicates.py`, folded into `ALL_PREDICATES` (contracts/memory-graph-vocabulary.md)
- [X] T005 Add `last_contact: datetime` field to the `Relationship` dataclass in `core/cognition/ze-memory/ze_memory/graph/types.py` (depends on T001)
- [X] T006 Extend `GraphStore.upsert_relationship`'s `ON CONFLICT (source_id, predicate, target_id) DO UPDATE` clause in `core/cognition/ze-memory/ze_memory/graph/store.py` to also advance `last_contact` to the newer of the existing/incoming values, alongside the existing `confidence = GREATEST(...)` bump (depends on T001, T005; data-model.md §3)

**Checkpoint**: `memory_relationships` has `last_contact`; `project`/`WORKS_ON`/`COLLABORATES_WITH` are recognized vocabulary; reinforcement advances `last_contact`. US1 and US2 implementation can now begin.

---

## Phase 3: User Story 1 - People and projects live in one connected graph (Priority: P1) 🎯 MVP

**Goal**: Extracting a project mention or a person-to-person collaboration
from conversation/email/calendar creates typed, provenanced graph state —
not rows in a second table — and repeat mentions reinforce rather than
duplicate.

**Independent Test**: Extract a project mention and a person's involvement
in it from a conversation; query `/brain/graph`/`GraphStore.expand()` from
either the person or the project entity and confirm the other is reachable
via a typed edge with confidence and provenance (quickstart.md, User Story
1).

### Tests for User Story 1

- [X] T007 [P] [US1] Test: conversation-episode extraction produces a `project` entity + `WORKS_ON` edge, in `plugins/ze-personal/tests/contacts/test_consolidator.py` (mock the LLM client — `client.complete`/`client.stream` — per Constitution V; no real LLM call)
- [X] T008 [P] [US1] Test: two people mentioned together with no project produces a `COLLABORATES_WITH` edge between their `person` entities, in `plugins/ze-personal/tests/contacts/test_consolidator.py` (mock the LLM client per Constitution V; no real LLM call)
- [X] T009 [P] [US1] Test: `GraphStore.upsert_relationship` reinforces (not duplicates) an existing `WORKS_ON`/`COLLABORATES_WITH` edge and advances `last_contact`, in `core/cognition/ze-memory/tests/graph/test_store.py` (mock the `asyncpg` pool with `AsyncMock` per Constitution V; no real DB)
- [X] T010 [P] [US1] Test: `zc029` migration drops `contact_relationships` cleanly with no data loss expected (empty table), in `plugins/ze-personal/tests/migrations/test_zc029.py` (or existing migration-test convention for this package)

### Implementation for User Story 1

- [X] T011 [US1] Add `ProjectProposal` and `RelationshipEdgeProposal` dataclasses to `plugins/ze-personal/ze_personal/contacts/types.py`, mirroring `ContactProposal`'s shape
- [X] T012 [US1] Extend `ContactsConsolidator._extract_candidates()`'s LLM prompt/output schema in `plugins/ze-personal/ze_personal/contacts/consolidator.py` to also emit project mentions and `WORKS_ON`/`COLLABORATES_WITH` edge mentions (depends on T011; research.md §4)
- [X] T013 [P] [US1] Extend `extract_email_contacts()` in `plugins/ze-personal/ze_personal/contacts/extractors.py` to emit project/collaboration mentions from email threads (depends on T011)
- [X] T014 [P] [US1] Extend `extract_calendar_contacts()` in `plugins/ze-personal/ze_personal/contacts/extractors.py` to emit project/collaboration mentions from calendar attendees (depends on T011)
- [X] T015 [US1] Extend the result-hook path in `plugins/ze-personal/ze_personal/graph/memory_hooks.py` to write `project` entities via `GraphStore.upsert_entity` and `WORKS_ON`/`COLLABORATES_WITH` edges via `GraphStore.upsert_relationship`, alongside the existing `contact_proposal_hook` (depends on T004, T012, T013, T014)
- [X] T016 [US1] Add a project-entity write helper mirroring `PersonStore._write_entity()`'s pattern (attrs mapping, silent-failure-logged upsert) in `plugins/ze-personal/ze_personal/graph/memory_hooks.py` (depends on T002, T015)
- [X] T017 [US1] Create migration `plugins/ze-personal/ze_personal/migrations/versions/zc029_drop_contact_relationships.py` (revision `zc029`, down_revision `zc028`): `DROP TABLE contact_relationships` (research.md §5)
- [X] T018 [US1] Remove `PersonRelationship` dataclass from `plugins/ze-personal/ze_personal/contacts/types.py`
- [X] T019 [US1] Remove `PersonStore.add_relationship()` and `PersonStore.get_relationships()` from `plugins/ze-personal/ze_personal/contacts/store.py` (depends on T018)
- [X] T020 [US1] Remove the `_domain("contacts.relationships", "contact_relationships", 20)` registration from `plugins/ze-personal/ze_personal/plugin.py`
- [X] T021 [US1] Remove the `contact_relationships` truncation entry from `core/ops/ze-onboarding/ze_onboarding/reset.py`
- [X] T022 [US1] Update `plugins/ze-personal/tests/contacts/test_person_store.py` and `test_types.py` to remove all `PersonRelationship`/`add_relationship`/`get_relationships` references (depends on T018, T019)

**Checkpoint**: Project entities and both new edge types flow from extraction into the graph with reinforcement; the dead `contact_relationships` schema no longer exists anywhere in the codebase (SC-001, SC-002).

---

## Phase 4: User Story 2 - Relationship state is honest about staleness (Priority: P2)

**Goal**: Every person↔person and person↔project edge's `confidence`
reflects real elapsed-time decay via the shared `decay()` function when
read, and `last_contact` only ever advances from processed communication
activity.

**Independent Test**: Create an edge, advance time past one `TIME_LINEAR`
decay period with no new activity, confirm `confidence` decayed via
`ze_agents.claims.decay()` — not a bespoke formula (quickstart.md, User
Story 2).

### Tests for User Story 2

- [X] T023 [P] [US2] Dedicated SC-004 test: construct/read a `Relationship` with `last_contact` 60+ days in the past and confirm `relationship.confidence.value` reflects `ze_agents.claims.decay(..., DecayProfile.TIME_LINEAR, elapsed_days=...)`'s output, in `core/cognition/ze-memory/tests/graph/test_store.py` (mock the `asyncpg` pool with `AsyncMock` per Constitution V; no real DB)
- [X] T024 [P] [US2] Test: `last_contact` only advances via `GraphStore.upsert_relationship` (processed communication-graph activity) — no code path allows a manual/user-supplied `last_contact`, in `core/cognition/ze-memory/tests/graph/test_store.py` (mock the `asyncpg` pool with `AsyncMock` per Constitution V; no real DB)
- [X] T025 [P] [US2] Test: an edge with no activity beyond creation reports `last_contact == created_at` (not null, not a guess), in `core/cognition/ze-memory/tests/graph/test_store.py` (mock the `asyncpg` pool with `AsyncMock` per Constitution V; no real DB)

### Implementation for User Story 2

- [X] T026 [US2] Retrofit `Relationship.confidence`'s type from `float` to `ze_agents.claims.Confidence` in `core/cognition/ze-memory/ze_memory/graph/types.py` (depends on T005; contracts/memory-graph-vocabulary.md)
- [X] T027 [US2] Implement read-time decay hydration in `GraphStore`'s row→`Relationship` construction (`list_relationships`/`expand`) in `core/cognition/ze-memory/ze_memory/graph/store.py`: `Confidence(value=decay(stored_float, DecayProfile.TIME_LINEAR, elapsed_days=(now - last_contact).days), decay_profile=DecayProfile.TIME_LINEAR)` (depends on T006, T026; research.md §2)
- [X] T028 [US2] Grep `core/cognition/ze-memory` and `plugins/ze-personal` for any caller reading a `Relationship.confidence` as a bare float and update it to `.value` (depends on T026)

**Checkpoint**: Reading any relationship edge at any time reflects honest, real decay; `last_contact` is trustworthy (SC-004).

---

## Phase 5: User Story 3 - Stale-relationship nudges compete fairly for the user's attention (Priority: P2)

**Goal**: The existing `StaleFollowUpNudge` signal is ranked by
`PriorityView` alongside loops/goals/hypotheses and surfaced only when it
wins the shared attention budget — not as an independent, unranked
channel.

**Independent Test**: With loops, goals, and stale relationships all
eligible on the same day and the shared budget covering only one, confirm
`PriorityView` surfaces whichever it ranks highest — including a stale
relationship when it wins (quickstart.md, User Story 3).

**Note**: This story does not depend on Phase 2/US1/US2 — it is scoped
entirely to `core/arbitration/ze-priority` and `plugins/ze-personal/ze_personal/jobs/
briefing.py`, and may be implemented in parallel with them.

### Tests for User Story 3

- [X] T029 [P] [US3] Test: `PriorityView.rank()` ranks a relationship item against loop/goal/hypothesis items and surfaces whichever scores highest, in `core/arbitration/ze-priority/tests/test_view.py` (mock stores with `AsyncMock` per Constitution V; no real DB, no real LLM)
- [X] T030 [P] [US3] Test: `PriorityView.rank()` degrades gracefully when `relationship_source` raises — still returns ranked items from the sources that succeeded (FR-010), in `core/arbitration/ze-priority/tests/test_view.py` (mock stores with `AsyncMock` per Constitution V; no real DB)
- [X] T031 [P] [US3] Regression test: `PriorityView` constructed without a `relationship_source` (existing three-store signature) still works unchanged, in `core/arbitration/ze-priority/tests/test_view.py` (mock stores with `AsyncMock` per Constitution V; no real DB)
- [X] T032 [P] [US3] Test: `MorningBriefing.run()` reads its relationship-staleness line from `PriorityView`'s ranked output, not a direct `PersonStore.list_stale_for_follow_up()` call, in `plugins/ze-personal/tests/jobs/test_briefing.py` (mock `PriorityView`/`PersonStore` with `AsyncMock` per Constitution V; no real DB, no real LLM)

### Implementation for User Story 3

- [X] T033 [US3] Add `"relationship"` to the `SourceKind` `Literal` and add a `RelationshipSignal` dataclass (`name: str`, `days_ago: int`) to `core/arbitration/ze-priority/ze_priority/types.py`
- [X] T034 [US3] Define the `RelationshipStalenessSource` `Protocol` in `core/arbitration/ze-priority/ze_priority/types.py`, structurally matching `PersonStore.list_stale_for_follow_up(stale_days, limit) -> list[StaleFollowUpNudge]` (depends on T033; contracts/priority-relationship-source.md)
- [X] T035 [US3] Implement `score_relationship_staleness()` in `core/arbitration/ze-priority/ze_priority/scoring.py`, mirroring `score_loop`/`score_goal`/`score_hypothesis`'s signature and `sort_and_rank`-compatible `PriorityItem` output (depends on T033)
- [X] T036 [US3] Add an optional `relationship_source: RelationshipStalenessSource | None = None` constructor parameter to `PriorityView` in `core/arbitration/ze-priority/ze_priority/view.py` (depends on T034)
- [X] T037 [US3] Add a fourth try/except source block to `PriorityView.rank()`; generalize the all-sources-failed hard-fail check from the hardcoded `3` to the number of sources actually supplied (depends on T035, T036)
- [X] T038 [US3] Wire the concrete `PersonStore` instance into `PriorityView`'s `relationship_source` argument in `apps/ze-api/ze_api/container.py` (depends on T036)
- [X] T039 [US3] Add a `priority_view: PriorityView` constructor dependency to `MorningBriefing` in `plugins/ze-personal/ze_personal/jobs/briefing.py`, wired via the job's existing DI registration (depends on T037)
- [X] T040 [US3] Replace `briefing.py`'s direct `person_store.list_stale_for_follow_up(self._stale_days, self._max_nudges)` call with a read of `PriorityView.rank()`'s items filtered to `source_kind == "relationship"` (depends on T039)

**Checkpoint**: Stale-relationship nudges rank fairly against every other attention-competing source; the briefing no longer bypasses the shared budget (SC-003).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T041 [P] Update `specs/README.md`'s phase 128 row from 📝 Draft to ✅ Done (Constitution I — status updated in the same commit as implementation)
- [X] T042 Run `specs/phases/128-social-cognition-foundation/quickstart.md` end-to-end against a local `make dev` + `make db-up && make migrate`
- [X] T043 [P] `make lint` and `make test-memory && make test-priority && make test-personal && make test-onboarding`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately. **Blocks US1 and US2 only.**
- **US1 (Phase 3)**: Depends on Foundational (Phase 2) completion.
- **US2 (Phase 4)**: Depends on Foundational (Phase 2) completion. Independent of US1 (touches the same files as US1's T015/T016 only incidentally — T026/T027 build on T005/T006 from Foundational, not on US1's extraction work).
- **US3 (Phase 5)**: **No dependency on Foundational, US1, or US2** — entirely scoped to `core/arbitration/ze-priority` and `briefing.py`. Can be implemented in parallel with Phase 2-4 by a different contributor/session.
- **Polish (Phase 6)**: Depends on whichever of US1/US2/US3 are in scope for the release being validated; T042 (quickstart) requires all three for full validation.

### Parallel Opportunities

- T002, T003, T004 (Foundational) can run in parallel — different concerns within the same or adjacent files.
- T007, T008, T009, T010 (US1 tests) can run in parallel.
- T013, T014 (US1 extractors) can run in parallel once T011 lands.
- T023, T024, T025 (US2 tests) can run in parallel.
- T029, T030, T031, T032 (US3 tests) can run in parallel.
- **US3's entire phase (T029-T040) can run in parallel with Phase 2/US1/US2**, since it touches no shared file.

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together:
Task: "Test: conversation extraction produces project entity + WORKS_ON edge in plugins/ze-personal/tests/contacts/test_consolidator.py"
Task: "Test: two people mentioned together produce a COLLABORATES_WITH edge in plugins/ze-personal/tests/contacts/test_consolidator.py"
Task: "Test: GraphStore.upsert_relationship reinforces an edge and advances last_contact in core/cognition/ze-memory/tests/graph/test_store.py"
Task: "Test: zc029 migration drops contact_relationships cleanly in plugins/ze-personal/tests/migrations/test_zc029.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational.
2. Complete Phase 3: User Story 1.
3. **STOP and VALIDATE**: run quickstart.md's User Story 1 section independently.
4. This alone satisfies SC-001 and SC-002 — the graph-consolidation half of the phase.

### Incremental Delivery

1. Foundational → US1 (MVP: projects/edges in the graph, dead schema gone).
2. Add US2 (honest decay) → validate independently → SC-004 satisfied.
3. Add US3 (fair-ranked nudges, independent of the above) → validate independently → SC-003 satisfied.
4. Each story adds value without breaking the others — US1/US2 touch `core/cognition/ze-memory`+`ze-personal` extraction/contacts code, US3 touches `core/arbitration/ze-priority`+`ze-personal` briefing code, with no file overlap between US3 and US1/US2.

### Parallel Team Strategy

With two contributors: one completes Foundational → US1 → US2 sequentially (shared files); the other starts US3 immediately in parallel, since it has zero dependency on Phase 2-4.

---

## Notes

- [P] tasks touch different files with no unmet dependency.
- Every implementation task cites the exact file path from plan.md's Project Structure.
- Tests are written before their corresponding implementation task within each story, per Constitution V.
- Verify each story's tests fail before implementing, then pass after.
- Commit after each task or logical group, split by user story (per AGENTS.md's commit-splitting convention).
