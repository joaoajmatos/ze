---

description: "Task list for Open-Loop Drift Detection & Surfacing (Phase B)"

---

# Tasks: Open-Loop Drift Detection & Surfacing

**Input**: Design documents from `/specs/phases/110-open-loop-drift-surfacing/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/surfacing.md (all present)

**Tests**: Included — plan.md's Constitution Check (Test Discipline) explicitly names the test
files this feature adds/extends; they are treated as planned, not optional.

**Organization**: Tasks are grouped by user story (US1 = drift detection P1, US2 = inline
surfacing P1, US3 = push surfacing P2) per spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to
- File paths are exact, relative to repo root

---

## Phase 1: Setup

**Purpose**: Package dependency and governance-doc groundwork for the new
`ze-worldstate → ze-correlation` edge (ratified by Clarification; needed before any code that
imports `ze_correlation` from `ze_worldstate`).

- [X] T001 Add `"ze-correlation"` to `core/ze-worldstate/pyproject.toml` dependencies
- [X] T002 Update the package dependency graph table in `CLAUDE.md`: `ze-worldstate` row gains
      `ze-correlation`, same commit as T001 (constitution Governance principle)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, type, and store changes shared by all three user stories (drift state,
rationale field, evidence-freshness signal, REST visibility). No user story can be implemented
until this phase is done.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create migration `core/ze-worldstate/ze_worldstate/migrations/versions/zw002_drift_columns.py`
      adding `drift_deadline TIMESTAMPTZ NULL`, `drift_rationale TEXT NULL` to `open_loops`, plus
      partial index `open_loops_drift_deadline_idx ON open_loops (drift_deadline) WHERE state = 'active'`
- [X] T004 [P] Add `drift_deadline: datetime | None` and `drift_rationale: str | None` fields to
      the `OpenLoop` dataclass in `core/ze-worldstate/ze_worldstate/types.py`
- [X] T005 Add `LoopState.ACTIVE: {..., LoopState.DRIFTING}` edge to `_ALLOWED_TRANSITIONS` in
      `core/ze-worldstate/ze_worldstate/store.py` (depends on T004)
- [X] T006 Add `set_drift_deadline(loop_id, deadline)`, `set_drift_rationale(loop_id, rationale)`,
      `list_drift_candidates()` to the `LoopStore` Protocol and `PostgresLoopStore` in
      `core/ze-worldstate/ze_worldstate/store.py` (depends on T003, T004, T005)
- [X] T007 Extend `link_evidence` in `core/ze-worldstate/ze_worldstate/store.py` to also execute
      `UPDATE open_loops SET updated_at = now() WHERE id = $1` alongside its existing
      `memory_relationships` insert (depends on T003)
- [X] T008 [P] Add `drift_rationale` (nullable, additive) to the loop REST payload in
      `core/ze-worldstate/ze_worldstate/rest.py` and, if declared separately, the schema in
      `apps/ze-api/ze_api/api/routes/loops.py` (depends on T004)

**Checkpoint**: Foundation ready — `OpenLoop` carries drift fields, the store can read/write
them, `ACTIVE → DRIFTING` is a legal transition, and the field is visible over REST.

---

## Phase 3: User Story 1 - A stalling commitment is quietly flagged as drifting (Priority: P1) 🎯 MVP

**Goal**: An `active` loop past its implied (or default 7-day) window with no corroborating
evidence transitions to `drifting` with a stored, evidence-cited, inference-tagged rationale —
via a scheduled sweep, or immediately when a contradiction is written.

**Independent Test**: Seed an `active` loop with an elapsed implied window and no corroborating
evidence; run the drift sweep; verify the loop is `drifting` with a rationale and that no
notification was sent. Separately, contradict a loop's cited evidence and verify immediate
transition without waiting for the sweep.

### Implementation for User Story 1

- [X] T009 [P] [US1] Add `DEFAULT_DRIFT_WINDOW_DAYS` constant and drift-window computation
      helpers in new `core/ze-worldstate/ze_worldstate/drift.py`
- [X] T010 [US1] Add `compose_absence_rationale()` and
      `compose_contradiction_rationale(evidence_type, evidence_id)` rationale-composition
      helpers in `core/ze-worldstate/ze_worldstate/drift.py` (depends on T009)
- [X] T011 [US1] Add optional `implied_window_days: int | None` field to the extraction gate's
      JSON response schema (`_SYSTEM_PROMPT`, `_ExtractionGateResult`) in
      `core/ze-worldstate/ze_worldstate/extraction.py`
- [X] T012 [US1] Set `drift_deadline = confirmed_at + timedelta(days=implied_window_days or
      DEFAULT_DRIFT_WINDOW_DAYS)` in `core/ze-worldstate/ze_worldstate/review.py::confirm_loop`
      (depends on T006, T009, T011)
- [X] T013 [US1] Set `drift_deadline` on the direct-declared-active path in
      `core/ze-worldstate/ze_worldstate/extraction.py` (depends on T012)
- [X] T014 [US1] Extend `cascade_from_evidence` in `core/ze-worldstate/ze_worldstate/decay.py`:
      when an affected loop is `ACTIVE`, transition it to `DRIFTING` and write a rationale via
      `drift.compose_contradiction_rationale` (depends on T005, T010)
- [X] T015 [US1] Create `DriftSweepJob` in `core/ze-worldstate/ze_worldstate/jobs/drift_sweep.py`:
      use `list_drift_candidates()`, the eligibility predicate from `drift.py`, transition
      eligible loops to `DRIFTING`, and `set_drift_rationale` via
      `compose_absence_rationale()` (depends on T006, T009, T010)
- [X] T016 [US1] Wire `DriftSweepJob` construction into
      `core/ze-worldstate/ze_worldstate/bootstrap.py` (depends on T015)
- [X] T017 [US1] Register the drift sweep job in `apps/ze-api/ze_api/compose.py` and add
      `worldstate.drift{window_days, cron}` to `apps/ze-api/config/config.yaml` (depends on T016)
- [X] T018 [P] [US1] Test `core/ze-worldstate/tests/test_drift.py` — window computation,
      rationale composition, sweep-eligibility predicate
- [X] T019 [P] [US1] Test `core/ze-worldstate/tests/jobs/test_drift_sweep.py` — elapsed window +
      no evidence drifts; fresh evidence stays active; non-`active` states untouched (FR-004);
      transient failure mid-batch leaves already-processed transitions intact and retries the
      rest next run
- [X] T020 [US1] Extend `core/ze-worldstate/tests/test_decay.py` for FR-002 — immediate
      contradiction transitions an `active` loop to `drifting` without a sweep (depends on T014)

**Checkpoint**: User Story 1 is fully functional and independently testable — drift sweep and
immediate contradiction path both produce hedged, evidence-cited `drifting` transitions visible
over REST; nothing is auto-closed/dropped/confirmed.

---

## Phase 4: User Story 2 - A drifting loop is mentioned inline when the topic comes up (Priority: P1)

**Goal**: A `drifting` loop sharing a linked entity with the current turn's resolved entities
earns a hedged inline mention in the response, via a dedicated orchestration node that runs
alongside (not inside) the correlation engine's inline node, with no new package dependency.

**Independent Test**: Reference an entity linked to a `drifting` loop in a turn; verify the
response includes a hedged mention. Send an unrelated turn; verify no mention appears and no
loop state changes.

### Implementation for User Story 2

- [X] T021 [US2] Create `LoopSurfacer.inline_candidates(entity_ids)` in
      `core/ze-worldstate/ze_worldstate/surfacing.py`, matching `drifting` loops by entity-link
      overlap only (reusing Phase A's entity-resolution/matching infrastructure, no new
      embedding call); results carry `mention_text` built via new
      `format_hedged_mention(loop.title, loop.drift_rationale)` helper in `surfacing.py`, not
      raw rationale text (FR-009) (depends on Phase 2 completion)
- [X] T022 [US2] Wire `LoopSurfacer` construction into
      `core/ze-worldstate/ze_worldstate/bootstrap.py` (depends on T021)
- [X] T023 [P] [US2] Create `core/ze-core/ze_core/orchestration/nodes/loop_surfacing.py`,
      structurally mirroring `nodes/correlation.py`: reads
      `config["configurable"].get("loop_surfacer")`, returns `{}` immediately if absent, calls
      `surfacer.inline_candidates(entity_ids)` otherwise, catches and logs
      (`inline_loop_surfacing_error`) any exception; the node's text-section append uses
      `mention.mention_text` verbatim (already hedged), not a separately composed string
- [X] T024 [US2] Wire a `"surface_loops"` node into
      `core/ze-core/ze_core/orchestration/graph.py`, sequenced
      `execute_tool → correlate → surface_loops → (route)`, appending independently to
      `state["components"]` / `final_response` via the existing dict-merge pattern (depends on
      T023)
- [X] T025 [US2] Inject `loop_surfacer` into the graph's `config["configurable"]` in
      `apps/ze-api/ze_api/container.py`, same construction/injection shape as
      `correlation_engine` (depends on T022, T024)
- [X] T026 [US2] Write a `worldstate_loop_inline:{loop_id}` `push_log` row via `PushLogStore` on
      every inline mention, inside `core/ze-worldstate/ze_worldstate/surfacing.py` (depends on
      T021)
- [X] T027 [P] [US2] Test `core/ze-worldstate/tests/test_surfacing.py` — entity-overlap match
      surfaces a mention; no overlap produces no mention; repeated relevant turns may mention
      again (no novelty/budget gate on inline); mention text returned by `inline_candidates`
      starts with the hedged-phrasing prefix ("It looks like"), never a bare rationale string
      (FR-009)
- [X] T028 [P] [US2] New node test in `core/ze-core/tests/` for `surface_loops` — present/absent
      `loop_surfacer` in `config["configurable"]`, exception handling, matching how
      `nodes/correlation.py` is tested

**Checkpoint**: User Story 1 AND 2 both work independently — inline mentions appear only on
topical overlap and never mutate loop state.

---

## Phase 5: User Story 3 - A high-confidence drifting loop earns a proactive nudge (Priority: P2)

**Goal**: A `drifting` loop clearing confidence, relevance, grounding, novelty, and a sibling
daily push budget earns exactly one push notification, reusing (not duplicating) the correlation
engine's push-bar mechanics, with an inline-then-push cooldown and an immediate re-check before
sending.

**Independent Test**: Seed a `drifting` loop clearing every push-bar condition; run the push
sweep; verify exactly one notification and one `push_log` row; verify a loop failing any single
condition produces no push; verify no re-push within the novelty window or budget exhaustion.

### Implementation for User Story 3

- [X] T029 [US3] Extract `passes_confidence(confidence, tau)`,
      `passes_relevance(relevance, tau)`,
      `passes_novelty(summary, recent_summaries, embedder, max_similarity)`,
      `passes_grounding(summary, evidence_labels, nli_client, threshold)`,
      `within_budget(push_log, event_key, max_per_day, window_hours=24.0)` as free functions in
      `core/ze-correlation/ze_correlation/push.py`
- [X] T030 [US3] Refactor `CorrelationPushConsumer._passes_push_bar` to call the extracted
      functions, behavior-preserving (depends on T029)
- [X] T031 [P] [US3] Extend `core/ze-correlation/tests/test_push.py` to confirm the extracted
      functions are behavior-preserving (existing suite continues to pass unmodified) (depends
      on T029, T030)
- [X] T032 [US3] Add `passes_push_bar(loop, rationale)` to `LoopSurfacer` in
      `core/ze-worldstate/ze_worldstate/surfacing.py`, calling the five extracted functions with
      `event_key="worldstate_loop_push"`, plus the inline-cooldown gate —
      `not await push_log.was_sent_within_hours(f"worldstate_loop_inline:{loop_id}",
      cooldown_hours)`. Requires a new `relevance_model: RelevanceModel` constructor param on
      `LoopSurfacer`, scoring the loop's linked entity names via `relevance_model.build()` /
      `.score(rset, entity_names, topics=[])` (research.md §7) (depends on T021, T026, T029,
      Setup T001/T002)
- [X] T033 [US3] Create `PushSweepJob` in `core/ze-worldstate/ze_worldstate/jobs/push_sweep.py`:
      select `drifting` loops, call `passes_push_bar`, re-check current lifecycle state
      immediately before sending (FR-011), send the notification, log a `push_log` row with
      `event_type="worldstate_loop_push"`; push notification body is
      `format_hedged_mention(loop.title, loop.drift_rationale)`, mirroring
      `CorrelationPushConsumer._maybe_push`'s templated body rather than a bare rationale dump
      (FR-009) (depends on T032)
- [X] T034 [US3] Add a `relevance_model: RelevanceModel` field to `CorrelationStack` in
      `core/ze-correlation/ze_correlation/bootstrap.py`, populated from the existing local
      `relevance_model` variable in `build_correlation_stack` (no behavior change to
      `CorrelationEngine`'s own use of it) (depends on Setup T001/T002)
- [X] T035 [US3] Wire `PushSweepJob` construction into
      `core/ze-worldstate/ze_worldstate/bootstrap.py`; `LoopSurfacer` construction now also takes
      the `RelevanceModel` instance from `correlation.relevance_model` on the `CorrelationStack`
      already returned by `build_correlation_stack(...)` in `apps/ze-api/ze_api/container.py`
      (container.py:223) — reuse that instance, don't construct a second one (depends on T033,
      T034)
- [X] T036 [US3] Register the push sweep job in `apps/ze-api/ze_api/compose.py` and add
      `worldstate.push{enabled, cron, budget, thresholds: {tau_confidence, tau_relevance, ...}}`
      to `apps/ze-api/config/config.yaml` (depends on T035)
- [X] T037 [P] [US3] Test `core/ze-worldstate/tests/jobs/test_push_sweep.py` — clears all bars →
      exactly one push; re-run within novelty window → no second push; budget exhausted → no
      push until reset (and correlation engine's own budget is unaffected); grounding failure →
      no push; relevance below threshold → no push; loop closed between sweep selection and send
      → no push (FR-011); inline mention then immediate sweep → no push within cooldown
      (FR-012), pushable after cooldown elapses; pushed notification body uses the hedged
      template, not raw `drift_rationale` (FR-009)
- [X] T038 [P] [US3] Extend `core/ze-worldstate/tests/test_surfacing.py` for `passes_push_bar`
      cases (depends on T032)

**Checkpoint**: All user stories are independently functional — drift detection, inline
surfacing, and push surfacing each work standalone and in combination, with no autonomous
lifecycle transitions beyond `active → drifting`.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T039 Run all five `quickstart.md` scenarios end-to-end against a running `make dev` +
      `make migrate` stack
- [X] T040 [P] Verify `apps/ze-api/ze_api/migrate.py`'s `zw` chain discovery picks up
      `zw002_drift_columns.py` automatically (verification only, no code change expected)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001, needed before any `ze_correlation` import
  lands, though Phase 2 itself doesn't import it yet) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion only
- **User Story 2 (Phase 4)**: Depends on Foundational completion only — does not depend on US1's
  sweep/decay code, only on the shared `drifting` state and `OpenLoop` fields
- **User Story 3 (Phase 5)**: Depends on Foundational completion; also depends on US2's
  `surfacing.py`/`LoopSurfacer` scaffolding (T021, T026) and the inline `push_log` event key it
  establishes, and on Setup's `ze-correlation` dependency (T001/T002) for T029
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on US2/US3 — independently testable via direct sweep
  invocation and contradiction-path test, per quickstart §1–2
- **User Story 2 (P1)**: No dependency on US1's job code — independently testable by seeding a
  `drifting` loop directly (bypassing the sweep) and sending a turn, per quickstart §3
- **User Story 3 (P2)**: Builds on US2's `LoopSurfacer`/inline-log plumbing (shares
  `surfacing.py` and the `worldstate_loop_inline` push-log key); test it by seeding a `drifting`
  loop directly, per quickstart §4–5

### Within Each User Story

- Types/store/migration (Foundational) before any story work
- Rationale/window helpers before the sweep/decay call sites that use them
- `LoopSurfacer` scaffolding (US2) before push-bar extension (US3)
- Job creation before job wiring (`bootstrap.py`) before job registration (`compose.py`)
- Story implementation before its tests are extended to green (tests may be written first per
  Test Discipline, but must pass before the story checkpoint)

### Parallel Opportunities

- T001 and T002 can run together (different files)
- T004 and T008 can run in parallel once T003 lands (different concerns on `types.py`/`rest.py`)
- Once Foundational (Phase 2) completes, US1 and US2 can proceed in parallel — they touch
  disjoint files (`drift.py`/`decay.py`/`jobs/drift_sweep.py` vs. `surfacing.py`/`ze-core` nodes)
- US3 should start only after US2's T021/T026 land, since it extends the same `surfacing.py`
- All test tasks marked [P] within a phase can run in parallel with each other

---

## Parallel Example: User Story 1

```bash
Task: "Add DEFAULT_DRIFT_WINDOW_DAYS constant and drift-window computation helpers in core/ze-worldstate/ze_worldstate/drift.py"
Task: "Test core/ze-worldstate/tests/test_drift.py"
```

## Parallel Example: User Story 2

```bash
Task: "Create core/ze-core/ze_core/orchestration/nodes/loop_surfacing.py"
Task: "Test core/ze-worldstate/tests/test_surfacing.py"
Task: "New node test in core/ze-core/tests/ for surface_loops"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks all stories)
3. Complete Phase 3: User Story 1 (drift detection)
4. **STOP and VALIDATE**: run quickstart.md §1–2 independently
5. Deploy/demo if ready — "attention" half of the executive-function gap is no longer empty even
   before any surfacing exists

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → validate via quickstart §1–2 (MVP)
3. User Story 2 → validate via quickstart §3 (both P1 stories now complete)
4. User Story 3 → validate via quickstart §4–5 (P2, the higher-risk delivery surface)
5. Each story adds value without breaking previous stories — no lifecycle transition beyond
   `active → drifting` is ever introduced, so US2/US3 cannot regress US1's safety guarantees

### Parallel Team Strategy

With multiple developers, after Foundational completes:

- Developer A: User Story 1 (`drift.py`, `decay.py`, `jobs/drift_sweep.py`)
- Developer B: User Story 2 (`surfacing.py` inline path, `ze-core` node/graph wiring)
- Developer C: joins after US2's `surfacing.py` scaffolding lands, to build User Story 3
  (`ze-correlation` extraction, `jobs/push_sweep.py`)
