---

description: "Task list for Attention Arbitration — PriorityView + Shared Push Budget"

---

# Tasks: Attention Arbitration — PriorityView + Shared Push Budget

**Input**: Design documents from `/specs/phases/123-attention-arbitration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/priority_view.md, quickstart.md (all present)

**Tests**: Ze's constitution (Principle V, NON-NEGOTIABLE) requires tests for every feature — test tasks below are mandatory, not optional. Unit tests mock stores with `AsyncMock`; no real DB, no real LLM.

**Organization**: Tasks are grouped by user story (US1/US2/US3, priorities P1/P2/P3 from spec.md) so each can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1/US2/US3)

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `core/ze-priority/pyproject.toml` and `core/ze-priority/ze_priority/__init__.py` package skeleton, depending on `ze-agents`, `ze-proactive`, `ze-worldstate`, `ze-automation`, `ze-correlation`
- [X] T002 [P] Add `ze-priority` as a workspace member (root `pyproject.toml` / `uv.lock` regeneration)
- [X] T003 [P] Add `ze-priority` to `apps/ze-api/pyproject.toml` dependencies
- [X] T004 [P] Add `test-priority` target to `Makefile` following the existing `test-<package>` pattern

**Checkpoint**: `core/ze-priority` package exists, installable, empty test suite passes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared attention-budget primitive and PriorityView's base types — every user story depends on at least one of these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Create `core/ze-priority/ze_priority/types.py` with `PriorityItem`, `LoopSignal`/`GoalSignal`/`HypothesisSignal` (`SourceSignal` union), and `PriorityRanking` dataclasses per data-model.md — for goal-sourced items, `claim_kind` is `ClaimKind.PRIORITY`, assigned by `PriorityView` itself (goals carry no source-level claim kind), not read off `Goal`/`StuckGoal`
- [X] T006 [P] Create `core/ze-priority/ze_priority/errors.py` with `ZePriorityError(ZeError)`
- [X] T007 Create `core/ze-proactive/ze_proactive/attention_budget.py` with `ATTENTION_PUSH_EVENT_KEY`, `within_budget()`, `try_claim_shared()`, `release_shared()` per contracts/priority_view.md — logic moved from `core/ze-correlation/ze_correlation/push.py`'s existing `within_budget()`/`_PUSH_LOG_KEY`
- [X] T008 [P] Write `core/ze-proactive/tests/test_attention_budget.py` covering `within_budget`, atomic `try_claim_shared` (mocked `PushLogStore`), and `release_shared`
- [X] T009 Update `core/ze-correlation/ze_correlation/push.py`: remove local `within_budget`/`_PUSH_LOG_KEY`, import from `ze_proactive.attention_budget`, update `CorrelationPushConsumer._within_budget()` and its claim/release call sites to use `try_claim_shared`/`release_shared` with `source_kind="hypothesis"`
- [X] T010 Update `core/ze-worldstate/ze_worldstate/surfacing.py`: change the `within_budget` import from `ze_correlation.push` to `ze_proactive.attention_budget`; update `LoopSurfacer.claim_push`/`release_push_claim` to call `try_claim_shared`/`release_shared` with `source_kind="loop"`
- [X] T011 Replace `correlation.push.max_pushes_per_day`, `correlation.salience.budget.max_pushes_per_day`, and `worldstate.push.budget.max_pushes_per_day` in `apps/ze-api/config/config.yaml` with a single `proactive.budget.max_pushes_per_day: 3` key (migrated value = min of the two prior effective values, per spec Clarifications)
- [X] T012 Update `core/ze-proactive/ze_proactive/bootstrap.py` to read `proactive.budget.max_pushes_per_day` and expose it for constructor injection into consumers of the shared budget
- [X] T013 Update `core/ze-correlation` and `core/ze-worldstate` bootstrap wiring (`ze_correlation` consumer construction, `ze_worldstate/bootstrap.py`) to source `max_pushes_per_day` from the shared `proactive.budget` config instead of their own now-removed YAML keys

**Checkpoint**: Shared budget primitive lives in `ze-proactive` under one config key and one event key; both `ze-correlation` and `ze-worldstate` compile and their existing tests pass against it. No ranking exists yet.

---

## Phase 3: User Story 1 - Seeing one ranked list of what's open (Priority: P1) 🎯 MVP

**Goal**: A single `PriorityView.rank()` query returns one ordered list spanning open loops, stuck/near-gate goals, and non-stale hypotheses, each carrying its source claim-kind and a comparable `Confidence`-based score.

**Independent Test**: Seed one drifting `OpenLoop`, one `StuckGoal` (idle days since last progress), one recent `Hypothesis` (confidence 0.4) against mocked stores; call `PriorityView.rank()`; assert all three appear, each tagged with source type and a resolved rank (spec.md Acceptance Scenario 1).

### Tests for User Story 1

- [X] T014 [P] [US1] Unit test: `PriorityView.rank()` combines three mocked sources into one ordered list with correct `source_kind`/`signal` passthrough, in `core/ze-priority/tests/test_view.py`
- [X] T015 [P] [US1] Unit test: a 10-day-drifting loop ranks above a 1-hour-old low-confidence hypothesis (spec.md Acceptance Scenario 2), in `core/ze-priority/tests/test_view.py`
- [X] T016 [P] [US1] Unit test: deterministic tie-break by `activity_at` then `source_id` on equal `Confidence.value`, in `core/ze-priority/tests/test_scoring.py`
- [X] T017 [P] [US1] Unit test: graceful degradation — `HypothesisStore` raises, `rank()` still returns loop/goal items with `sources_failed == {"hypothesis"}` (spec.md Edge Cases); plus a second case where all three stores raise, asserting `ZePriorityError` is raised (contracts/priority_view.md), in `core/ze-priority/tests/test_view.py`
- [X] T017a [P] [US1] Unit test: a `PriorityItem`/`PriorityRanking` round-trips into a valid `Priority`-kind claim shape (`ClaimKind.PRIORITY` + `Confidence`, no missing fields) — FR-004's "must not preclude future Contribution-seam integration" — in `core/ze-priority/tests/test_view.py`

### Implementation for User Story 1

- [X] T018 [US1] Implement `core/ze-priority/ze_priority/scoring.py`: per-source `Confidence` adapters (loop `OpenLoop.confidence`/`state` via `TIME_LINEAR`; goal `StuckGoal.idle_days` via `ze_agents.claims.decay()` with `TIME_LINEAR`; hypothesis `confidence`+`relevance` via `EVIDENCE_WEIGHTED`) plus the deterministic tie-break comparator, per research.md
- [X] T019 [US1] Implement `core/ze-priority/ze_priority/view.py`: `PriorityView.__init__(loop_store, goal_store, hypothesis_store)`, `rank()` (queries all three, per-source try/except degrading into `sources_failed`, raises `ZePriorityError` only if all three fail, sorts via scoring.py, assigns 1-indexed `rank`, sets `claim_kind=ClaimKind.PRIORITY` on goal-sourced items), and `rank_subset(candidates)` per contracts/priority_view.md
- [X] T020 [US1] Wire `PriorityView` construction into `apps/ze-api/ze_api/container.py` (constructor injection of the existing `LoopStore`/`GoalStore`/`HypothesisStore` instances)

**Checkpoint**: `PriorityView` is fully functional and independently testable — no budget/arbitration behavior depends on it yet.

---

## Phase 4: User Story 2 - Ze surfaces the most-deserving item first (Priority: P2)

**Goal**: When both correlation and worldstate have eligible items to push the same day and the shared budget can't cover both, only the `PriorityView`-ranked-higher item is pushed.

**Independent Test**: Seed a lower-priority hypothesis and higher-priority drifting loop, both push-eligible, with one shared push remaining; run the arbitration sweep; assert only the loop is pushed and the hypothesis is logged as budget-arbitrated (spec.md Acceptance Scenario, User Story 2).

### Tests for User Story 2

- [X] T021 [P] [US2] Unit test: `AttentionArbitrationJob.run()` with one remaining budget slot claims and sends only the higher-ranked candidate; the other is logged as budget-arbitrated, not dropped, in `core/ze-priority/tests/test_arbitration.py`
- [X] T022 [P] [US2] Unit test: `AttentionArbitrationJob.run()` with zero remaining budget slots pushes neither candidate regardless of rank, in `core/ze-priority/tests/test_arbitration.py`
- [X] T023 [P] [US2] Unit test: a lost claim race (two candidates, first claim fails) falls through to the next-ranked eligible candidate, in `core/ze-priority/tests/test_arbitration.py`

### Implementation for User Story 2

- [X] T024 [US2] Add an eligibility-only candidate method to `LoopSurfacer` in `core/ze-worldstate/ze_worldstate/surfacing.py` (applies existing `passes_push_bar` novelty/relevance checks, returns candidates without sending or claiming)
- [X] T025 [US2] Add an equivalent eligibility-only `CorrelationPushCandidateSource` (or method on `CorrelationPushConsumer`) in `core/ze-correlation/ze_correlation/push.py`
- [X] T026 [US2] Implement `core/ze-priority/ze_priority/arbitration.py`: `AttentionArbitrationJob` (per contracts/priority_view.md) — gathers eligible candidates from both sources, ranks via `PriorityView.rank_subset()`, iterates ranked candidates calling `try_claim_shared`, delegates the winner to its source's existing send function, releases on send failure, logs remaining candidates as budget-arbitrated
- [X] T027 [US2] Remove `core/ze-worldstate/ze_worldstate/jobs/push_sweep.py` (`PushSweepJob`) and its dedicated tests, superseded by `AttentionArbitrationJob`
- [X] T028 [US2] Remove `ze-correlation`'s autonomous scheduled push-trigger registration (keep the extracted eligibility/send functions from T025), superseded by `AttentionArbitrationJob`
- [X] T029 [US2] Register `AttentionArbitrationJob` (`job_id = "attention_arbitration_sweep"`) in `apps/ze-api/ze_api/compose.py`, replacing the removed `PushSweepJob` and correlation trigger registrations

**Checkpoint**: US1 + US2 together fully replace both prior sweep jobs with one arbitrated sweep; existing per-mechanism eligibility bars (SC-004) are unchanged.

---

## Phase 5: User Story 3 - One attention budget, not two independent ones (Priority: P3)

**Goal**: The daily interruption budget is one configured number, not two separately-configured limits that happen to share a table.

**Independent Test**: Configure a shared `max_pushes_per_day`; exhaust it via correlation-only claims; assert a subsequent worldstate claim the same day is withheld by the shared check (spec.md Acceptance Scenario, User Story 3).

### Tests for User Story 3

- [X] T030 [P] [US3] Integration-style unit test: exhaust `proactive.budget.max_pushes_per_day` via three `try_claim_shared(..., source_kind="hypothesis", ...)` calls, then assert a fourth `try_claim_shared(..., source_kind="loop", ...)` call the same day returns `False`, in `core/ze-proactive/tests/test_attention_budget.py`

### Implementation for User Story 3

- [X] T031 [US3] Remove the now-dead fallback read of `correlation.salience.budget.max_pushes_per_day` from `ze_correlation`'s config loader (superseded by T009/T013's shared-config wiring), and grep the codebase for any remaining reference to the retired per-mechanism event keys (`correlation_push`, `worldstate_loop_push`) or config keys, updating/removing each

**Checkpoint**: Exactly one budget, one config key, one event key — verified by T030 exercising both mechanisms against the same counter.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T033 [P] Run all `quickstart.md` validation scenarios (User Stories 1–3 + degradation edge case) end-to-end
- [X] T034 [P] Update `CLAUDE.md`'s package dependency graph and "Adding a new plugin"-adjacent core-package listing to include `ze-priority`; add its migration-ownership row if applicable (none — no new tables)
- [X] T035 Update `specs/README.md` phase index row for Phase 123
- [X] T036 [P] Add a performance test seeding a synthetic tens-of-items working set (loops/goals/hypotheses) and asserting `PriorityView.rank()` completes in under 500ms (SC-001), in `core/ze-priority/tests/test_view.py`
- [X] T037 Run `make lint && make test-priority && make test-proactive && make test-correlation && make test-worldstate` and fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (shared budget primitive and base types are needed before any story's tests can run)
- **User Story 1 (Phase 3)**: Depends on Foundational only — independently testable and shippable as the MVP
- **User Story 2 (Phase 4)**: Depends on Foundational **and** User Story 1 (`AttentionArbitrationJob` calls `PriorityView.rank_subset`, built in US1) — not independent of US1 despite the spec's story-priority ordering
- **User Story 3 (Phase 5)**: Depends on Foundational only (the shared budget primitive from Phase 2 already satisfies US3's core claim; Phase 5 mainly removes remaining dead per-mechanism config and adds the cross-mechanism regression test) — can run in parallel with Phase 3/4
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3 — true MVP
- **US2 (P2)**: Hard dependency on US1 (uses `PriorityView`) — cannot be built or tested independently of US1's implementation, only of US3's polish tasks
- **US3 (P3)**: No dependency on US1/US2 — the shared budget itself is delivered in Foundational; Phase 5 is a small independent cleanup + verification

### Parallel Opportunities

- T002, T003, T004 in parallel (Setup)
- T005, T006, T008 in parallel (Foundational; T007/T009/T010/T011/T012/T013 are sequential — same files / dependent config)
- T014–T017a in parallel (US1 tests, before T018–T020)
- T021–T023 in parallel (US2 tests, before T024–T029)
- Phase 5 (US3) can proceed in parallel with Phase 3/4 once Phase 2 is done, since it touches different files (`ze_correlation`'s config loader, grep-and-fix) than US1/US2's ranking/arbitration code — except T031/T032 should land after T009 to avoid merge conflicts in `push.py`

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (after Foundational, before implementation):
Task: "Unit test PriorityView.rank() combines three mocked sources in core/ze-priority/tests/test_view.py"
Task: "Unit test drift-duration vs hypothesis-recency ranking in core/ze-priority/tests/test_view.py"
Task: "Unit test deterministic tie-break in core/ze-priority/tests/test_scoring.py"
Task: "Unit test graceful degradation on source failure in core/ze-priority/tests/test_view.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (shared budget primitive + base types)
3. Complete Phase 3: User Story 1 — `PriorityView.rank()` is now usable by any internal caller (e.g. a future "what's open" summary), independent of any push behavior change
4. **STOP and VALIDATE**: run quickstart.md's User Story 1 section
5. Ship as MVP — this alone closes the doctrine's "nothing produces Priority claims" gap

### Incremental Delivery

1. Setup + Foundational → shared budget primitive live, both mechanisms unaffected in behavior
2. Add User Story 1 → `PriorityView` ships, informational only
3. Add User Story 2 → arbitration goes live, `PushSweepJob` and correlation's autonomous trigger retired
4. Add User Story 3 → dead config removed, cross-mechanism budget sharing regression-tested
5. Polish

---

## Notes

- [P] tasks touch different files with no incomplete dependency
- US2 is **not** independent of US1 despite lower spec priority number sequencing — implement in the order Setup → Foundational → US1 → US2 → US3, not by priority label alone
- Commit after each task or logical group
- `make lint` and the affected packages' `make test-<name>` must pass before any task is considered done (Constitution Principle V)
