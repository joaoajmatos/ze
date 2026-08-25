---

description: "Task list for Contribution Seam Core — Typed Proposals + Reflection Migration"
---

# Tasks: Contribution Seam Core — Typed Proposals + Reflection Migration

**Input**: Design documents from `/specs/phases/124-contribution-seam-core/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no `contracts/` — internal feature)

**Tests**: Included — the spec requires dedicated rejection tests per producer (SC-001) and this
repo's constitution (Principle V, NON-NEGOTIABLE) mandates tests for every feature.

**Organization**: Tasks are grouped by user story (P1/P1/P2 per spec.md) to enable independent
implementation and testing of each story.

**Revision note**: This version incorporates the `/speckit-analyze` remediation pass (7 findings
resolved: OpenLoop's and Signal's real write paths are now explicitly gated per Edge Case 1;
dream-pipeline `confidence` source, `decay_profile`, and `target_face` are now decided;
promotion-gate non-regression and the `CLAUDE.md` dependency-graph update are now tracked).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project (monorepo, multiple existing core/plugin packages modified) — see plan.md
Project Structure for the authoritative file map.

---

## Phase 1: Setup

**Purpose**: Wire the new cross-package dependency edge (`ze-plugin` → consumed by
`ze-memory`/`ze-worldstate`/`ze-correlation`) before any code imports it.

- [X] T001 [P] Add `"ze-plugin"` to `dependencies` (and `[tool.uv.sources]`) in `core/ze-memory/pyproject.toml`
- [X] T002 [P] Add `"ze-plugin"` to `dependencies` (and `[tool.uv.sources]`) in `core/ze-worldstate/pyproject.toml`
- [X] T003 [P] Add `"ze-plugin"` to `dependencies` (and `[tool.uv.sources]`) in `core/ze-correlation/pyproject.toml`
- [X] T004 Run `make install` (uv sync) at repo root to regenerate lockfiles for T001-T003

**Checkpoint**: `ze_plugin.contribution` importable from `ze-memory`, `ze-worldstate`, `ze-correlation`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared `Contribution` type, licensing table, and validation guard function that
all three user stories build on (per spec: "Every other user story depends on this type existing
first").

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Add `ContributionError(ZeCoreError)`, `UnlicensedClaimKindError`, `MissingEvidenceError`, `DanglingEvidenceError` to `core/ze-agents/ze_agents/errors.py` (research.md §10)
- [X] T006 [P] Create `SourceFunction` and `TargetFace` `StrEnum`s plus the `_LICENSE: dict[SourceFunction, frozenset[ClaimKind]]` table in `core/ze-plugin/ze_plugin/contribution.py` (FR-001, FR-007; research.md §2-§3) — wire `PERCEPTION: {FACT}`, `REFLECTION: {INFERENCE, SUSPICION}`, `EXECUTIVE: {IDENTITY, FACT, INFERENCE, SUSPICION, PRIORITY}`; other functions present with empty/full sets as placeholders per doctrine, no producer yet
- [X] T007 Create `EvidenceRef` and `Contribution` dataclasses in `core/ze-plugin/ze_plugin/contribution.py` (FR-001; data-model.md) — depends on T006
- [X] T008 Implement `validate_and_submit()` in `core/ze-plugin/ze_plugin/contribution.py`: claim-kind licensing check (FR-007), non-empty-evidence check for INFERENCE/SUSPICION (FR-011), per-kind evidence-existence dispatch via injected `check_fact_exists`/`check_episode_exists`/`check_signal_exists` callables (FR-011; research.md §8), structured `WARNING` rejection log via `get_logger` before raising (FR-012; research.md §9) — depends on T005, T007
- [X] T009 [P] Write `core/ze-plugin/tests/test_contribution.py`: licensing table accepts/rejects per `SourceFunction` (FR-007, Edge Case 1), missing-evidence rejection (FR-011), dangling-evidence rejection via a fake failing existence-check callable (FR-011), rejection emits a `contribution_rejected` WARNING log (FR-012) — depends on T008

**Checkpoint**: `Contribution` + `validate_and_submit()` exist and are fully unit-tested in isolation. All three user stories can now proceed.

---

## Phase 3: User Story 1 - A shared `Contribution` type exists and `Signal`/`OpenLoop` use it (Priority: P1) 🎯 MVP

**Goal**: `Signal` and `OpenLoop` are each expressible as a `Contribution` without any
producer-local duplicate metadata field, and each producer's real write path enforces the
general licensing check (FR-007, Edge Case 1) the same way reflection's does.

**Independent Test**: Construct a `Contribution` from a `Signal` and from an `OpenLoop`
candidate; assert both round-trip with `claim_kind`/`provenance`/`confidence` populated from
`ze_agents.claims`, and that `Signal.magnitude` stays distinct from `confidence`. Separately,
submit a mistagged `Signal`/`OpenLoop` contribution through each producer's real write path and
assert rejection (Edge Case 1).

### Tests for User Story 1

- [X] T010 [P] [US1] Write `core/ze-memory/tests/test_contribution.py`: `signal_to_contribution()` round-trips a `Signal` into a `FACT`-kind `Contribution` with `magnitude` and `confidence` distinct, `decay_profile=TIME_LINEAR` (Acceptance Scenario 1, SC-003, research.md §12)
- [X] T011 [P] [US1] Write `core/ze-worldstate/tests/test_contribution.py`: `loop_to_contribution()` round-trips an `OpenLoop` preserving its existing `claim_kind`/`confidence` without duplication, and maps each `LoopProvenance` value to the correct epistemic `Provenance` per the research.md §5 table (Acceptance Scenario 2)

### Implementation for User Story 1

- [X] T012 [US1] Write migration `core/ze-memory/ze_memory/migrations/versions/zm018_signal_provenance.py`: add `provenance TEXT NOT NULL DEFAULT 'synthesized'` to `memory_signals`, then drop the default (FR-002; research.md §7, zm017 precedent)
- [X] T013 [P] [US1] Add `provenance: Provenance` field to `Signal` in `core/ze-memory/ze_memory/types.py` (FR-002) — depends on T012
- [X] T014 [P] [US1] Create `signal_to_contribution()` in `core/ze-memory/ze_memory/contribution.py`: `claim_kind` always `FACT`, `target_face=TargetFace.WORLD`, `source_function=SourceFunction.PERCEPTION`, `evidence=[]`, `decay_profile=DecayProfile.TIME_LINEAR` (FR-003; data-model.md; research.md §12) — depends on T013
- [X] T015 [US1] Set `provenance=Provenance.LIVE_SEARCH` on the `Signal(...)` construction in `plugins/ze-news/ze_news/signals.py` (`NewsSignalSource` polls external RSS — live external fetch)
- [X] T016 [US1] Set `provenance=Provenance.GRAPH_RECALL` on the `Signal(...)` construction in `plugins/ze-calendar/ze_calendar/signals.py` (`CalendarSignalSource` reads the user's own already-stored calendar/reminder data)
- [X] T017 [US1] Set `provenance` on both `Signal(...)` constructions in `plugins/ze-finance/ze_finance/signals/finance.py` (large-transaction / recurring-detection signals — reads the user's own stored transaction data, `Provenance.GRAPH_RECALL`)
- [X] T018 [US1] Set `provenance=Provenance.GRAPH_RECALL` on the `Signal(...)` construction in `plugins/ze-messenger/ze_messenger/signals.py` (`MessagingSignalSource` reads already-ingested inbound messages)
- [X] T019 [P] [US1] Create `loop_to_contribution()` and the `_INFLOW_TO_EPISTEMIC` mapping table in `core/ze-worldstate/ze_worldstate/contribution.py`, accepting an optional `evidence: list[EvidenceRef]` parameter (FR-004; research.md §5, §12) — depends on T007
- [X] T020 [US1] In `core/ze-worldstate/ze_worldstate/extraction.py`, wrap `_create_declared_loop`'s `loop_store.create()` call in `validate_and_submit()` using `loop_to_contribution()` (`claim_kind=PRIORITY`, `evidence=[]`, no existence-check callables needed) (FR-004 amended, Edge Case 1; research.md §5) — depends on T019
- [X] T021 [US1] In the same file, wrap `propose_loop_candidates()`'s gated/non-declared `loop_store.create()` call (the `claim_kind=SUSPICION` path) in `validate_and_submit()`, converting the existing `evidence_refs: list[ze_worldstate.types.EvidenceRef]` parameter into `contribution.EvidenceRef` entries and wiring real `check_fact_exists`/`check_episode_exists` callables (FR-004 amended, FR-011, Edge Case 1; research.md §5) — depends on T020
- [X] T022 [P] [US1] In `core/ze-worldstate/tests/test_contribution.py`, add a rejection test: a malformed `OpenLoop` contribution (a `claim_kind` not in `EXECUTIVE`'s license) submitted through `extraction.py`'s write path is rejected before `loop_store.create()` is called (Edge Case 1) — depends on T021
- [X] T023 [US1] In `core/ze-memory/ze_memory/retriever.py`, wrap `ingest_signal()`'s `INSERT INTO memory_signals` call in `validate_and_submit()` using `signal_to_contribution()` (`evidence=[]`, no existence-check callables needed) (FR-003 amended, Edge Case 1) — depends on T014
- [X] T024 [P] [US1] In `core/ze-memory/tests/test_contribution.py`, add a rejection test: a malformed `Signal` contribution (a `claim_kind` other than `FACT`) submitted through `ingest_signal()`'s write path is rejected before the insert runs (Edge Case 1) — depends on T023

**Checkpoint**: User Story 1 fully functional and testable independently — `Contribution` has
exactly two real producers, both round-tripping correctly and both enforcing the general
licensing check at their real write path, zero duplicate metadata fields.

---

## Phase 4: User Story 2 - Reflection cannot submit a fact (Priority: P1)

**Goal**: The dream pipeline's artifact-staging write and the correlation engine's
hypothesis-save write both reject any `claim_kind=FACT` contribution before anything is
persisted, and the existing promotion gate downstream of dream staging keeps working unchanged.

**Independent Test**: Submit a dream-staging `Contribution` tagged `claim_kind=FACT` — assert
rejection before any store write; submit the same tagged `INFERENCE`/`SUSPICION` — assert
success and that the existing promotion gate still runs on it unchanged. Repeat the rejection
check for correlation's hypothesis save.

### Tests for User Story 2

- [ ] T025 [P] [US2] Write `core/ze-memory/tests/dream/test_contribution_write_path.py`: a `claim_kind=FACT` artifact submission raises `UnlicensedClaimKindError` before `dream_store.save_artifact` is called (mock the store, assert not called); a `claim_kind=INFERENCE` submission persists exactly as before, with `confidence=Confidence(0.5, TIME_LINEAR)` and `target_face=SELF` (Acceptance Scenarios 1-2, SC-001; research.md §11, §13)
- [ ] T026 [P] [US2] In the same file, add `test_hindsight_fact_is_never_claim_kind_fact`: an `ArtifactType.HINDSIGHT_FACT` artifact tagged `claim_kind=INFERENCE` succeeds; tagged `claim_kind=FACT` is rejected — proves the artifact-type label never leaks into the claim-kind tag (research.md §6)
- [ ] T027 [US2] In the same file, add a promotion-gate non-regression test (FR-010): an artifact accepted by `validate_and_submit()` still proceeds through the existing `gates.py`/`promoter.py` NLI/critic pipeline unchanged — mock the promotion gate, assert it is still invoked with the same arguments it received pre-feature
- [ ] T028 [P] [US2] Write `core/ze-correlation/tests/test_contribution_write_path.py`: a `claim_kind=FACT` hypothesis submission raises `UnlicensedClaimKindError` before `hypothesis_store.save` is called; `claim_kind=SUSPICION` (correlation's actual current tagging) persists exactly as before, with `decay_profile=TIME_LINEAR` and `target_face=SELF` (Acceptance Scenario 3, SC-001; research.md §12, §13) — asserts the same validation logic as T025/T026, not a reimplementation (FR-006)

### Implementation for User Story 2

- [ ] T029 [US2] In `core/ze-memory/ze_memory/dream/dream_pass.py`, route all four `save_artifact()` call sites (`SYNTHESIZED_INSIGHT`, `SYNTHESIZED_PROCEDURE`, `HINDSIGHT_FACT`, `PLAN_STRESS_TEST`) through `validate_and_submit()`, always constructing the `Contribution` with `claim_kind=ClaimKind.INFERENCE`, `confidence=Confidence(value=0.5, decay_profile=DecayProfile.TIME_LINEAR)`, `target_face=TargetFace.SELF`, `source_function=SourceFunction.REFLECTION`, `evidence` built from each artifact's `source_fact_ids`/`source_episode_ids` (FR-005; research.md §11, §13) — depends on T008
- [ ] T030 [US2] In `core/ze-correlation/ze_correlation/engine.py`, wrap the `hypothesis_store.save(hypothesis)` call in `validate_and_submit()`, projecting `Hypothesis.evidence` (`EvidenceRef` with `.kind`/`.id`) into `contribution.EvidenceRef` entries, `confidence=Confidence(value=hypothesis.confidence, decay_profile=DecayProfile.TIME_LINEAR)`, `target_face=TargetFace.SELF`, `source_function=SourceFunction.REFLECTION` (FR-006; research.md §12, §13) — depends on T008
- [ ] T031 [US2] Wire real `check_fact_exists`/`check_episode_exists` callables at both `validate_and_submit()` call sites in T029/T030, backed by each package's existing store lookup methods (FR-011)

**Checkpoint**: The doctrine's "reflection may never emit a fact" rule is now enforced by the
type system for both reflection producers — this is the feature's actual payoff (User Story 2)
— and the existing promotion gate is confirmed unaffected (FR-010).

---

## Phase 5: User Story 3 - No behavior change for existing consumers (Priority: P2)

**Goal**: `ze-correlation` and `ze-worldstate` continue polling `signal_sources()` and producing
loops/hypotheses exactly as before this feature.

**Independent Test**: Run the existing `ze-correlation` and `ze-worldstate` integration test
suites unmodified; assert no behavior changes beyond call-boundary type-shape adaptations.

### Tests for User Story 3

- [ ] T032 [US3] Run `make test-correlation` and `make test-worldstate`; fix any test that fails due only to a call-boundary type-shape change introduced by T019-T024 or T029-T031 (e.g. a test constructing a bare `OpenLoop`/`Hypothesis` that now also needs a `Contribution`-shaped assertion) — no test's *assertions about surfaced loops/hypotheses/pushes* may change (Acceptance Scenario 1, SC-002, FR-008)

**Checkpoint**: All three user stories independently verified; zero regressions in existing
consumer behavior.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-wide consistency and final validation.

- [ ] T033 [P] Run `make lint` and fix any violations across `core/ze-plugin`, `core/ze-agents`, `core/ze-memory`, `core/ze-worldstate`, `core/ze-correlation`, and the four touched plugin packages
- [ ] T034 Run `make migrate` locally against `make db-up` to confirm `zm018_signal_provenance` applies cleanly on top of `zm017`
- [ ] T035 Execute `quickstart.md` end-to-end (all 5 scenarios) and confirm each expected outcome
- [ ] T036 [P] Update `CLAUDE.md`'s "Package dependency graph" table to add the three new edges this feature introduces (`ze-memory`, `ze-worldstate`, `ze-correlation` → `ze-plugin`)
- [ ] T037 Update spec.md **Status** from `Planned` to `Done` and add a row to `specs/README.md`'s phase index (Constitution Principle I, Development Workflow Definition of Done)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup (needs `ze-plugin` importable from the three consumer packages) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — no dependency on US2/US3
- **User Story 2 (Phase 4)**: Depends on Foundational (`validate_and_submit()`) — does NOT depend on US1's retrofits (Signal/OpenLoop), only on the shared guard function, so US1 and US2 can run in parallel if staffed
- **User Story 3 (Phase 5)**: Depends on US1 (T020-T024, real write-path gating landing) and US2 (T029-T031, reflection write-path gating landing), since it verifies their non-regression
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Within Each User Story

- Tests before implementation (write T010/T011 and confirm they fail against pre-feature code, then implement T012-T024; same pattern for T025-T028 → T029-T031)
- Migration (T012) before the `Signal` field it enables (T013)
- Type/conversion function before call-site wiring (T013→T014→T023; T007→T019→T020→T021)
- `_create_declared_loop`'s wrap (T020) before the gated-path wrap (T021) — same file, sequential edits

### Parallel Opportunities

- T001, T002, T003 (Setup) — different files
- T006 has no same-phase parallel peer (T005/T007/T008 are sequential dependencies within Foundational), but T009 can start once T008 lands
- T010, T011 (US1 tests) — different packages
- T013, T019 — different packages, both depend only on Foundational
- T015, T016, T017, T018 — four different plugin files, fully independent
- T022, T024 — different packages, once their respective wiring (T021, T023) lands
- T025, T026, T028 (US2 tests) — different files (T027 shares T025's file, sequential)
- T033 — independent of T034/T035/T036/T037
- T036 — independent of T034/T035/T037

---

## Parallel Example: User Story 1

```bash
# Once Foundational (Phase 2) is done, launch US1's independent conversion work together:
Task: "Create signal_to_contribution() in core/ze-memory/ze_memory/contribution.py"
Task: "Create loop_to_contribution() in core/ze-worldstate/ze_worldstate/contribution.py"

# The four SignalSource call-site updates are fully independent of each other:
Task: "Set provenance on Signal(...) in plugins/ze-news/ze_news/signals.py"
Task: "Set provenance on Signal(...) in plugins/ze-calendar/ze_calendar/signals.py"
Task: "Set provenance on Signal(...) in plugins/ze-finance/ze_finance/signals/finance.py"
Task: "Set provenance on Signal(...) in plugins/ze-messenger/ze_messenger/signals.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `make test-plugin test-memory test-worldstate` — confirm `Contribution` round-trips correctly for both existing producers, and both real write paths (`ingest_signal`, `loop_store.create`) enforce licensing
5. This alone delivers the doctrine's "one vocabulary" step, generally enforced, even before reflection is migrated

### Incremental Delivery

1. Setup + Foundational → shared type + guard function ready
2. User Story 1 → `Signal`/`OpenLoop` speak `Contribution`, real write paths gated → validate independently
3. User Story 2 → dream + correlation write paths gated, promotion gate confirmed unaffected → **the safety payoff ships** → validate independently (this is the feature's actual reason for existing)
4. User Story 3 → confirm zero regression → validate
5. Polish → lint, migration check, quickstart, dependency-graph doc update, spec status

### Parallel Team Strategy

With two developers: Developer A takes Foundational then US1 (Signal/OpenLoop retrofits and
write-path gating); Developer B waits only for T008 (`validate_and_submit()`) to land, then
starts US2 (dream + correlation write-path wiring) in parallel with A's US1 work, since US2 does
not depend on US1's retrofits — only on the shared guard function.

---

## Notes

- No `contracts/` phase — this feature has no external interface.
- [P] tasks = different files, no dependencies on incomplete same-phase work.
- Commit after each task or logical group.
- Verify T010/T011/T022/T024/T025/T026/T028 fail against pre-feature code before implementing (Constitution Principle V spirit — write the test, watch it fail for the right reason, then make it pass).
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence (US2 deliberately does not depend on US1's retrofits, only on Foundational).
