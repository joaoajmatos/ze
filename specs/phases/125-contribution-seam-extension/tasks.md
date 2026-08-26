---

description: "Task list for Contribution Seam Extension — Social Cognition + Action"
---

# Tasks: Contribution Seam Extension — Social Cognition + Action

**Input**: Design documents from `/specs/phases/125-contribution-seam-extension/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no `contracts/`
— internal feature)

**Tests**: Included — the spec requires a dedicated rejection test at the contact-store write
boundary (SC-001) and this repo's constitution (Principle V, NON-NEGOTIABLE) mandates tests for
every feature.

**Organization**: Tasks are grouped by user story (P1/P1/P2 per spec.md) to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project (monorepo, multiple existing core/plugin packages modified) — see plan.md
Project Structure for the authoritative file map.

---

## Phase 1: Setup

**Purpose**: Confirm the package dependency edges this feature needs already exist.

- [X] T001 Verify `plugins/ze-personal` → `ze-sdk` → `ze-plugin` and `ze-personal` → `ze_agents.*`
  (already used directly by `extractors.py`'s existing `from ze_agents.types import ToolCall`)
  resolve with no `pyproject.toml` changes — unlike Phase 124, this feature introduces **zero**
  new cross-package dependency edges (research.md §7a). No code change; a verification
  checkpoint only.

**Checkpoint**: No `make install` re-sync needed before Foundational work starts.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared licensing change and re-export module User Story 2's write-path
enforcement builds on.

**⚠️ CRITICAL**: US2 cannot begin until this phase is complete. US1 and US3 do not depend on
this phase's contents and MAY proceed in parallel with it (see Dependencies & Execution Order).

- [X] T002 [P] Flip `_LICENSE[SourceFunction.SOCIAL_COGNITION]` from `frozenset()` to
  `frozenset({ClaimKind.IDENTITY})` in `core/ze-plugin/ze_plugin/contribution.py` (FR-004;
  research.md §5) — the one core-package change this feature makes
- [X] T003 [P] Create `packages/ze-sdk/ze_sdk/contribution.py`: re-export `Contribution`,
  `EvidenceRef`, `SourceFunction`, `TargetFace`, `validate_and_submit` from
  `ze_plugin.contribution`, mirroring `ze_sdk/channels.py`'s existing re-export pattern
  (FR-003; data-model.md; research.md §7a) — required because `ze-personal` is a plugin and
  CLAUDE.md bars plugin code from importing `ze_plugin.*` directly
- [X] T004 [P] Write `packages/ze-sdk/tests/test_contribution.py`: each re-exported name imports
  from `ze_sdk.contribution` and is identical (`is`) to its `ze_plugin.contribution` original —
  depends on T003
- [X] T005 Update `core/ze-plugin/tests/test_contribution.py`: `SOCIAL_COGNITION` now accepts
  `claim_kind=IDENTITY` and rejects `FACT`/`INFERENCE`/`SUSPICION`/`PRIORITY` (FR-004) —
  depends on T002

**Checkpoint**: `SOCIAL_COGNITION` licensed for `IDENTITY` only, and `ze-personal`'s one legal
path to the seam (`ze_sdk.contribution`) exists and is tested. User Story 2 can now proceed.

---

## Phase 3: User Story 1 - Contact and relationship claims carry the shared vocabulary (Priority: P1) 🎯 MVP

**Goal**: `Person`, `PersonRelationship`, `ContactProposal`, and `PersonSource` carry
`claim_kind`/`provenance`/`confidence` from `ze_agents.claims`, persisted and round-tripped
through `PersonStore`, with zero loss of `SOURCE_WEIGHTS`-derived weighting behavior.

**Independent Test**: Construct a `Person` and a `ContactProposal` from a conversation
extraction. Assert both carry `claim_kind=IDENTITY`, a `Provenance` value derived from their
existing `source_type`, and a `Confidence` value derived from their existing bespoke
`confidence` float — with no loss of the existing `SOURCE_WEIGHTS`-derived weighting behavior.

### Tests for User Story 1

- [X] T006 [P] [US1] Write `plugins/ze-personal/tests/contacts/test_types.py`: constructing
  `Person`/`PersonSource`/`PersonRelationship`/`ContactProposal` defaults `claim_kind=IDENTITY`;
  `_SOURCE_TYPE_TO_PROVENANCE` maps each of `"manual"`/`"conversation"`/`"email"`/`"calendar"`/
  `"research"` to the correct `Provenance` per research.md §1's table, and an unrecognized
  `source_type` falls back to `Provenance.SYNTHESIZED` (Acceptance Scenarios 1-2)
- [X] T007 [P] [US1] Extend `plugins/ze-personal/tests/contacts/test_person_store.py`:
  `_person_from_row`/`_source_from_row` map `claim_kind`/`provenance` from row data;
  `upsert()`/`add_source()`/`add_relationship()`/`get_relationships()` round-trip the two new
  columns (Acceptance Scenarios 1-2)

### Implementation for User Story 1

- [X] T008 [US1] Add `claim_kind: ClaimKind`/`provenance: Provenance` fields and the module-level
  `_SOURCE_TYPE_TO_PROVENANCE: dict[str, Provenance]` mapping to `Person`, `PersonSource`,
  `PersonRelationship`, `ContactProposal` in
  `plugins/ze-personal/ze_personal/contacts/types.py` (FR-001, FR-002; data-model.md;
  research.md §1) — `confidence: float` stays unchanged on every type (SC-002); `decay_profile`
  is never stored on the dataclasses themselves, only constructed transiently at the
  `Contribution`-conversion boundary (T016) — depends on T006 (test-first)
- [X] T009 [US1] Write migration
  `plugins/ze-personal/ze_personal/migrations/versions/zc028_contacts_claim_kind.py`
  (`down_revision = "zc027"`): add `claim_kind TEXT NOT NULL` and `provenance TEXT NOT NULL` to
  `contacts`, `contact_sources`, `contact_relationships`, each with an unconditional
  `claim_kind = 'identity'` backfill and a `provenance` backfill derived from the row's own
  `source_type` via the research.md §1 mapping (FR-006; data-model.md schema table; research.md
  §6, mirroring the `zm016`/`zcor002` additive-column-plus-backfill pattern) — depends on T008
- [X] T010 [US1] Update `_person_from_row`/`_source_from_row` in
  `plugins/ze-personal/ze_personal/contacts/store.py` to map `claim_kind=ClaimKind(row["claim_kind"])`/
  `provenance=Provenance(row["provenance"])` from row data — depends on T008, T009
- [X] T011 [US1] Update `PersonStore.upsert()` (both the `person.id is not None` and the
  new-person INSERT branches) in `store.py` to write `claim_kind`/`provenance` columns —
  depends on T010
- [X] T012 [US1] Update `PersonStore.add_source()` in `store.py` to write
  `claim_kind`/`provenance` into the `contact_sources` INSERT — depends on T010
- [X] T013 [US1] Update `PersonStore.add_relationship()` (INSERT + `RETURNING *` mapping) and
  `get_relationships()` (row mapping) in `store.py` to write and return `claim_kind`/
  `provenance` on `contact_relationships` — depends on T010

**Checkpoint**: User Story 1 fully functional and testable independently — every constructed
and persisted `Person`/`PersonSource`/`PersonRelationship`/`ContactProposal` carries
`claim_kind=IDENTITY` and a correctly-mapped `provenance`, with `SOURCE_WEIGHTS`-derived
`confidence` behavior unchanged (SC-002).

---

## Phase 4: User Story 2 - Contact-store writes go through the validated write path (Priority: P1)

**Goal**: The contacts consolidator and the agent-turn contact-proposal hook both route their
real `PersonStore` writes through Phase 124's validated `Contribution` write path, which
rejects any social-cognition-originated write tagged with a `claim_kind` other than `IDENTITY`.

**Independent Test**: Submit a contact contribution tagged `claim_kind=FACT` (an incorrect
tagging) through `_store_candidate`'s write path. Assert it is rejected using the same general
licensing check Phase 124 built (FR-007 of that spec), not a new reimplementation.

### Tests for User Story 2

- [X] T014 [P] [US2] Write `plugins/ze-personal/tests/contacts/test_contribution.py`:
  `person_source_to_contribution()` round-trips a `PersonSource` into a `Contribution` with
  `claim_kind=ClaimKind.IDENTITY`, `provenance` taken from the source, `confidence.decay_profile
  =DecayProfile.EVIDENCE_WEIGHTED`, `target_face=TargetFace.USER`,
  `source_function=SourceFunction.SOCIAL_COGNITION`, `evidence=[]` — mirrors
  `ze_memory/tests/test_contribution.py`'s `signal_to_contribution()` test shape — depends on
  T008 (US1's `PersonSource` fields)
- [X] T015 [P] [US2] Extend `plugins/ze-personal/tests/contacts/test_consolidator.py`: a contact
  contribution mistagged `claim_kind=FACT` submitted through `_store_candidate` raises
  `UnlicensedClaimKindError` before `store.upsert()`/`store.add_source()` are called (mock the
  store, assert not called); a correctly-tagged `claim_kind=IDENTITY` contribution persists
  exactly as today's direct call would have (Acceptance Scenarios 1-2, SC-001) — write first,
  confirm it fails against pre-implementation code
- [X] T016 [P] [US2] Write `plugins/ze-personal/tests/graph/test_memory_hooks.py` (new file — no
  existing tests cover `memory_hooks.py`): the same FR-004 rejection test as T015, but through
  `_write_contact_proposals`'s write boundary — proves the licensing check is enforced at both
  real write sites, not just the consolidator's

### Implementation for User Story 2

- [X] T017 [US2] Create `person_source_to_contribution()` in
  `plugins/ze-personal/ze_personal/contacts/contribution.py`, importing `Contribution`/
  `SourceFunction`/`TargetFace` from `ze_sdk.contribution` and `ClaimKind`/`Confidence`/
  `DecayProfile` from `ze_agents.claims` (FR-003; data-model.md; research.md §7) — depends on
  T003 (Foundational), T008 (US1)
- [X] T018 [US2] In `consolidator.py::_store_candidate`, wrap the existing-person branch
  (`store.add_source(best.id, source)`) and the new-person branch (`store.upsert(person)` then
  `store.add_source(stored.id, source)`) each in `validate_and_submit()` using
  `person_source_to_contribution(source)` — matching/dedup logic itself untouched (FR-003,
  FR-004, FR-010) — depends on T017
- [X] T019 [US2] In `plugins/ze-personal/ze_personal/graph/memory_hooks.py::_write_contact_proposals`,
  wrap its own `person_store.add_source(...)` / `person_store.upsert(person)` +
  `add_source(...)` sequence in `validate_and_submit()` the same way (FR-003's "same write
  boundary" parity, research.md §7) — depends on T017

**Checkpoint**: User Story 2 fully functional and testable independently — FR-004's rejection
behavior is mechanically enforced at both real contact-store write boundaries (SC-001), with
zero behavior change for correctly-tagged writes.

---

## Phase 5: User Story 3 - Agent-proposed side effects carry the same shape (Priority: P2)

**Goal**: `AgentResult.memory_proposals`/`.contact_proposals` are typed against the seam's claim
vocabulary (`ClaimBearingProposal`) instead of a bare `list`, with `contact_proposals` actually
populated with vocabulary-carrying `ContactProposal` entries — without giving `core/ze-agents`
a new dependency on any downstream package.

**Independent Test**: Inspect `AgentResult.contact_proposals` after an agent turn that proposes
a contact. Assert entries are `ContactProposal`s carrying `claim_kind=IDENTITY`/`provenance`/
`confidence`, satisfying the new `ClaimBearingProposal` Protocol — not the current untyped
`list`.

### Tests for User Story 3

- [ ] T020 [P] [US3] Write `core/ze-agents/tests/test_types.py`: a `ContactProposal`-shaped
  object with `claim_kind`/`provenance`/`confidence` attributes satisfies
  `isinstance(x, ClaimBearingProposal)` (structural, `runtime_checkable`); `AgentResult()`'s
  `memory_proposals`/`contact_proposals` default to `[]` typed `list[ClaimBearingProposal]`
  (Acceptance Scenario 1)
- [ ] T021 [P] [US3] Extend `plugins/ze-personal/tests/contacts/test_extractors.py`: constructed
  `ContactProposal`s from both `extract_email_contacts` and `extract_calendar_contacts` carry
  `claim_kind=IDENTITY` and the `Provenance` matching their `source_type` (`"email"`→
  `LIVE_SEARCH`, `"calendar"`→`LIVE_SEARCH`) (Acceptance Scenario 1) — depends on T008

### Implementation for User Story 3

- [ ] T022 [US3] Add the `runtime_checkable` `ClaimBearingProposal` `Protocol`
  (`claim_kind: ClaimKind`, `provenance: Provenance`, `confidence: float`) to
  `core/ze-agents/ze_agents/types.py`, importing only `ze_agents.claims` (no new cross-package
  edge — FR-005; data-model.md; research.md §3) — depends on T020 (test-first)
- [ ] T023 [US3] Retype `AgentResult.memory_proposals`/`.contact_proposals` to
  `list[ClaimBearingProposal]` in the same file (was untyped `list`) — depends on T022
- [ ] T024 [US3] Update `extract_email_contacts`/`extract_calendar_contacts` in
  `plugins/ze-personal/ze_personal/contacts/extractors.py` to populate `claim_kind=ClaimKind.IDENTITY`
  and `provenance=_SOURCE_TYPE_TO_PROVENANCE[...]` on each constructed `ContactProposal`
  (FR-001, FR-005) — depends on T008 (US1), T021 (test-first)

**Checkpoint**: User Story 3 fully functional and testable independently — `AgentResult`'s
proposal fields are seam-typed with zero new `ze-agents` import edges (Principle III intact),
and `contact_proposals` is actually populated with vocabulary-carrying entries end to end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide consistency and final validation.

- [ ] T025 [P] Run `make lint` and fix any violations across `plugins/ze-personal`,
  `packages/ze-sdk`, `core/ze-plugin`, `core/ze-agents`
- [ ] T026 Run `make migrate` locally against `make db-up` to confirm `zc028_contacts_claim_kind`
  applies cleanly on top of `zc027`
- [ ] T027 Execute `quickstart.md` end-to-end (all 5 scenarios) and confirm each expected outcome
- [ ] T028 Update spec.md **Status** from `Planned` to `Done`, and flip `specs/README.md`'s
  phase-125 row from `🔄 In Progress` to `✅ Done` (Constitution Principle I, Development
  Workflow Definition of Done) — no `CLAUDE.md` package-dependency-graph update needed, this
  feature introduces zero new edges (unlike Phase 124)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: No dependency on Setup's outcome beyond its verification —
  BLOCKS User Story 2 only (T017 needs `ze_sdk.contribution` and T002's licensing flip to mean
  anything); does NOT block US1 or US3
- **User Story 1 (Phase 3)**: Depends on nothing but Setup — can start immediately, in parallel
  with Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational (T002, T003) AND on US1's `PersonSource`
  fields (T008) — cannot start until both land
- **User Story 3 (Phase 5)**: Depends on US1 (T008, for `ContactProposal`'s fields) — does NOT
  depend on US2 (AgentResult typing never touches the write path)
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Within Each User Story

- Tests before implementation (T006/T007 before T008-T013; T014-T016 before T017-T019;
  T020/T021 before T022-T024)
- `types.py` fields (T008) before the migration that persists them (T009)
- Migration (T009) before `store.py`'s row-mapping update (T010), which precedes the
  write-method updates that depend on it (T011-T013)
- `person_source_to_contribution()` (T017) before either write-boundary wrap (T018, T019)
- `ClaimBearingProposal` Protocol (T022) before `AgentResult`'s retyping (T023)

### Parallel Opportunities

- T002, T003 (Foundational) — different files, no shared dependency
- T006, T007 (US1 tests) — different files
- T011, T012, T013 — same file (`store.py`) but disjoint methods; safe to parallelize by method,
  sequential if one contributor
- T014, T015, T016 (US2 tests) — different files
- T018, T019 (US2 implementation) — different files, both depend only on T017
- T020, T021 (US3 tests) — different packages
- US1 (Phase 3) can run fully in parallel with Foundational (Phase 2) — see Phase Dependencies
- T025 — independent of T026/T027/T028

---

## Parallel Example: Foundational + User Story 1

```bash
# Foundational and US1 have no shared dependency — launch together:
Task: "Flip _LICENSE[SOCIAL_COGNITION] in core/ze-plugin/ze_plugin/contribution.py"
Task: "Create packages/ze-sdk/ze_sdk/contribution.py re-export module"
Task: "Add claim_kind/provenance fields to Person/PersonSource/PersonRelationship/ContactProposal
       in plugins/ze-personal/ze_personal/contacts/types.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 3: User Story 1 (Foundational is not a hard blocker for US1 — see Phase
   Dependencies)
3. **STOP and VALIDATE**: `make test-personal -- -k "test_types or test_person_store"` —
   confirm every contact/relationship type carries the vocabulary and round-trips through
   `PersonStore`
4. This alone finishes the vocabulary-consistency gap for the type layer, even before the write
   path or `AgentResult` are touched

### Incremental Delivery

1. Setup (+ Foundational, in parallel) → shared licensing/re-export ready
2. User Story 1 → types + migration + store round-trip → validate independently (MVP)
3. User Story 2 → both real write boundaries mechanically enforce `IDENTITY`-only → validate
   independently (this is FR-004's actual payoff — mirrors Phase 124's User Story 2)
4. User Story 3 → `AgentResult` seam-typed with zero new import edges → validate independently
5. Polish → lint, migration check, quickstart, spec status

### Parallel Team Strategy

With two developers: Developer A takes Foundational then US2 (needs T002/T003 landed, plus
US1's T008); Developer B takes US1 directly (no dependency on Foundational), then US3 once US1's
T008 lands. US2 and US3 can then proceed in parallel — US2 does not touch `AgentResult`, and US3
does not touch the write path.

---

## Notes

- No `contracts/` phase — this feature has no external interface.
- [P] tasks = different files, no dependencies on incomplete same-phase work.
- Commit after each task or logical group.
- Verify T006/T007/T014-T016/T020/T021 fail against pre-feature code before implementing
  (Constitution Principle V spirit).
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence
  (US3 deliberately does not depend on US2, only on US1's type fields).
