---

description: "Tasks for phase 203 Open-Loop Lifecycle"
---

# Tasks: Open-Loop Lifecycle

**Input**: Design documents from `specs/phases/203-open-loop-lifecycle/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required (spec FR-012, SC-001, SC-004). Each story starts with a test through the real interface that fails on today's code. Every lifecycle event has a test-pg test in `apps/ze-api/tests/pg/` (`pytestmark = pytest.mark.pg`, `pg_pool` fixture, run with `make test-pg`). Callers are unit-tested against `AsyncMock(spec=LoopLifecycle)`, never a mocked pool.

**Organization**: Tasks are grouped by user story (spec.md US1–US3). The contract step comes first. Integration and cleanup come after the lane merges, because deleting the old store writes before every caller has moved would break the build.

## Format: `[ID] [P?] [Lane] [Tag] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Lane]**: The crew lane from plan.md's Lane Plan: `[L:lead]`, `[L:callers]`, `[L:inflow]`, `[L:docs]`. A task touches only files its lane owns.
- **[Tag]**: `[BE]` backend, `[WEB]` web app, `[PLATFORM]` tests infrastructure and gates, `[DOCS]` documentation
- **[Story]**: The user story (US1–US3)

**Crew**: the Maestro staffs one agent per lane (Sonnet `lead`, `callers`, `inflow`; Haiku `docs`). The contract step (`[L:lead]`, T001–T006) lands first; `callers` and `inflow` then run in parallel in their own worktrees and are reviewed as each finishes.

Paths below are relative to the repo root. `WS` = `core/cognition/ze-worldstate/ze_worldstate`, `WST` = `core/cognition/ze-worldstate/tests`, `PG` = `apps/ze-api/tests/pg`.

---

## Phase 1: Contract step (blocking)

**Purpose**: The types, signatures, rules and test fixtures every lane codes against. Nothing here deletes or changes behavior; the build stays green.

- [x] T001 [L:lead] [BE] Write `WST/test_lifecycle_rules.py` first: one parametrized row per `(LoopEvent, LoopState)` pair for the twelve non-create events (60 rows) plus the two create events' target states, each asserting the `Verdict` and `to_state` from data-model.md's table; plus the four FR-003 rules as named tests (`A→D` only by DECAY/DRIFT, `D→A` only by TRACK, `S→C` only by RESOLVE, `S→A` only by CONFIRM/TRACK/PROMOTE). Then create `WS/lifecycle/rules.py` (`LoopEvent`, `Verdict`, `EventRule`, `EVENT_RULES`, `verdict()`, `allowed_from()`, `DeclaredStamp` with `CONFIDENCE`, `DEFAULT_WINDOW_DAYS` and `sql()`, `SUSPECTED_CONFIDENCE`, and the confidence-stamp fragment moved verbatim from `store._CONFIDENCE_STAMP`; the store keeps its copy until T035) per contracts/lifecycle-events.md. Pure, no I/O. `make test-worldstate` green.
- [x] T002 [P] [L:lead] [BE] Create `WS/decision.py` (`CommitKind`, `GateKind`, `CommitDecision`, `CommitOutcome`, `CommitResult`) per contracts/inflow-commit.md, with `WST/test_decision.py` (frozen, defaults, `title`/`window_days` default `None`).
- [x] T003 [L:lead] [BE] Create `WS/lifecycle/events.py` with `LoopLifecycle` (constructor per contract; every event method with its signature and a docstring stating its guard and writes from data-model.md, body `raise NotImplementedError`) and the value types `LoopDraft`, `Corroboration`, `SourceWrite`, `Tracked`; `WS/lifecycle/__init__.py` exports `LoopLifecycle`, `LoopEvent`, `DeclaredStamp`, `LoopDraft`, `Corroboration`, `SourceWrite`, `Tracked`.
- [x] T004 [L:lead] [BE] In `WS/types.py`, change `LoopAdmission`: `decision: CommitDecision`; add `text: str = ""` and `inflow: str = ""`; keep `source` and `commit` for now (`commit` is deleted in T037, after lane `inflow` stops using it). Drop the `loop_judge` import (use `decision.CommitDecision`). Existing tests that build a `LoopAdmission` with a `LoopGateDecision` still pass (same attribute names).
- [x] T005 [L:lead] [BE] Wiring: `WS/bootstrap.py` builds `LoopLifecycle(pool, memory_store=shared.memory_store, nli_client=shared.nli_client)`, sets `WorldstateStack.lifecycle` and `deps[LoopLifecycle]`; `apps/ze-api/ze_api/wiring/hooks.py::wire_collision_detection` also sets the lifecycle's collision store; the ze-api container exposes `loop_lifecycle`; `apps/ze-api/ze_api/api/deps.py` gains `get_loop_lifecycle`. Update `WST/test_bootstrap.py` and `apps/ze-api/tests/agents/test_bootstrap.py`.
- [x] T006 [L:lead] [PLATFORM] `PG/conftest.py`: create, once per session after migrations, the test-only table `ze_test_faults(table_name text primary key)` and a `BEFORE INSERT OR UPDATE` trigger on `open_loops`, `memory_relationships` and `open_loop_sources` that raises when `TG_TABLE_NAME` is in it (research R9); add `ze_test_faults` to `RESET_TABLES`; add a `fail_writes_to(pool, table)` helper. `PG/_builders.py::make_loop` seeds with plain SQL (`INSERT … RETURNING *`, all lifecycle columns settable). Add `PG/test_fault_trigger_pg.py` proving the trigger raises and the reset clears it.

**Checkpoint**: Contract merged into `203-open-loop-lifecycle`. `callers` and `inflow` start.

---

## Phase 2: User Story 1 — A loop is never left half-changed (Priority: P1) 🎯 MVP

**Goal**: confirm, close, drop, expire, decay and drift are each one atomic write; drop and expire record the fingerprint with the state.

**Independent Test**: `make test-pg -k lifecycle` — each event stamps every field it owns; with the second table forced to fail, drop and expire leave the loop unchanged; decay after a sweep does not drift twice.

### Tests for User Story 1

- [x] T007 [L:lead] [BE] [US1] Write `PG/test_loop_lifecycle_pg.py` (US1 part), failing on the `NotImplementedError` bodies: `confirm` stamps state, 0.9, `confirmed_at`, deadline now+7d, rationale NULL and returns the stored row (US1-2); `confirm` on an active loop raises `InvalidLoopTransitionError`, on a missing id `LoopNotFoundError`; `close` from A and D, refused from S; `drop` from S/A/D writes state, `closed_at` and the fingerprint of the loop's evidence in one statement, and with `open_loops` forced to fail leaves neither the state change nor the fingerprint (US1-1, FR-006); `expire` drops a suspected loop with its fingerprint, writes a `NULL` fingerprint when the loop has no evidence, returns `None` for any other state; `decay_from_evidence` lowers confidence, moves A→D with the contradiction rationale in one statement, changes only confidence on S/D/C/X (edge case); a loop drifted by `drift` and then decayed keeps its sweep rationale (US1-3); two concurrent `decay_from_evidence` calls on one loop compose (the second reads the first's confidence under the lock); `drift` moves only an active loop past its deadline and returns `None` for a loop confirmed again after the candidate read.

### Implementation for User Story 1

- [x] T008 [L:lead] [BE] [US1] Implement `confirm`, `close`, `drop`, `expire`, `decay_from_evidence` and `drift` in `WS/lifecycle/events.py` per research R2/R3 (guarded `UPDATE … WHERE state = ANY(allowed_from(event))`, `FOR UPDATE` before drop/expire read the evidence and before decay reads confidence and the evidence count, `NULL` fingerprint on an evidence-less expire, fingerprint via `fingerprint.compute_evidence_fingerprint`, rationales via `drift.compose_*`). One log line each, with the names in the contract's "Logs once" rule. T007 green.
- [x] T009 [L:lead] [BE] [US1] Move the jobs and the contradiction hook onto the lifecycle: `WS/jobs/drift_sweep.py` and `WS/jobs/stale_suspicion.py` take `loop_store` (candidate reads) and `lifecycle`, and call `lifecycle.drift` / `lifecycle.expire`; `WS/bootstrap.py` passes both; `apps/ze-api/ze_api/wiring/hooks.py::install_contradiction_hook` calls `worldstate.lifecycle.decay_from_evidence("fact", fact_id)`; delete `WS/decay.py` and `WST/test_decay.py` (covered by T007); update `WST/jobs/test_drift_sweep.py` and `WST/jobs/test_stale_suspicion.py` to mock the lifecycle.
- [x] T010 [P] [L:callers] [BE] [US1] `WS/rest.py` `confirm_loop`, `close_loop`, `drop_loop` take `lifecycle: LoopLifecycle`; `apps/ze-api/ze_api/api/v0/loops/router.py` injects it with `Depends(get_loop_lifecycle)` for the three write routes (reads keep `get_loop_store`); 404/409 mapping unchanged. Update `WST/test_rest.py` and `apps/ze-api/tests/api/test_loops_route.py` first (they fail until the routes use the lifecycle).
- [x] T011 [P] [L:callers] [BE] [US1] `WS/agents/tools.py`: `confirm_loop`, `close_loop`, `drop_loop` take `lifecycle: LoopLifecycle` and call it; results and undo payloads unchanged. Update `WST/test_confirm_loop_tool.py`, `WST/test_loop_agent_cancel.py`, `apps/ze-api/tests/test_undo_payload_contract.py`, `apps/ze-api/tests/test_tool_asks_first_audit.py`.
- [ ] T012 [L:callers] [BE] [US1] Delete `WS/review.py` and `WST/test_review.py`; nothing imports them after T010–T011 (`grep -rn "ze_worldstate.review\|from ze_worldstate import review"` is empty).

**Checkpoint**: US1 works through REST, tools and jobs; existing pg tests still pass because the store's old writes still exist.

---

## Phase 3: User Story 2 — Every way into and out of a loop follows the same rules (Priority: P1)

**Goal**: both creates, track, note evidence, corroborate, promote, resolve and link go through the lifecycle with the one declared stamp.

**Independent Test**: `make test-pg -k lifecycle` (US2 part) plus T001's table test.

### Tests for User Story 2

- [x] T013 [L:lead] [BE] [US2] Extend `PG/test_loop_lifecycle_pg.py`, failing first: `create_declared` and `create_suspected` write the row, evidence links, entity links and the origin source together, and with `open_loop_sources` forced to fail write nothing (SC-001); both creates put the evidence on the contribution and pass the existence checkers (assert through a recording collision store); a `track_loop`-style declared create (no evidence, a conversation source) and an inflow declared create produce rows with identical stamp fields (US2-1, SC-002); `track` returns `confirmed`/`reinforced`/`revived` from S/A/D, refuses C/X, stamps S and D, only raises confidence on A (US2-2); `note_evidence` moves an active loop's deadline only when evidence is given, never lowers a later deadline, refuses C/X; `corroborate` writes links, the source row and the capped confidence, and a duplicate source key writes no confidence; `promote` from S stamps `GREATEST(c, 0.7)` with `promoted = true`; two concurrent `promote` calls on one loop give one `promote` and one `lost_race`, and the loser writes no confidence; `resolve` closes S/A/D with evidence and no fingerprint, returns `None` for C/X (US2-3); `link` sets reminder then goal once, returns `False` on a terminal loop.

### Implementation for User Story 2

- [x] T014 [L:lead] [BE] [US2] Implement `create_suspected` and `create_declared` in `WS/lifecycle/events.py`: build the contribution with `loop_to_contribution(loop, evidence=…, entity_ids=…)` for both, call `submit_and_detect_collisions` with the existence checkers from `memory_store` and a writer that runs the whole create transaction (research R5). Declared provenance is the draft's (the inflow maps conversation → `user_declared`).
- [x] T015 [L:lead] [BE] [US2] Implement `track`, `note_evidence`, `link` and `resolve` (move 199's `store.resolve` SQL here unchanged).
- [x] T016 [L:lead] [BE] [US2] Implement `corroborate` and `promote` per data-model.md, including `lost_race`. T013 green.
- [x] T017 [L:lead] [BE] [US2] Move the lead-owned pg tests off the store's write methods onto lifecycle events or `make_loop`: `PG/test_drift.py`, `PG/test_acceptance.py`, `PG/test_loop_claim_kind_pg.py`, `PG/test_loop_confidence_prior_pg.py`, `PG/test_loop_confirmation_pg.py`, `PG/test_loop_link_pg.py`, `PG/test_loop_sources_pg.py`, `PG/test_loops_since_pg.py`. Tests that only exercised a deleted store method (e.g. `test_stamp_declared_stamps`) are rewritten against the event that owns the behavior. `make test-pg` green.
- [x] T018 [L:callers] [BE] [US2] `WS/tracking.py`: `LoopTracker(loop_store, lifecycle, graph_store, entity_resolver, embedder)`; `track(title, window_days, session_id=None)`; no match → `lifecycle.create_declared(LoopDraft(title, USER_DECLARED, entity_ids=…, source=SourceKey(CONVERSATION, session_id) if session_id else None), window_days=window)`; a match → `lifecycle.track(match.id, window_days=window, entity_ids=…)`. Delete `_stamp`, `_create`, `_link_entities` and the direct `submit_and_detect_collisions` call; read the default window and the declared confidence from `lifecycle.DeclaredStamp`, not `drift` or `types`. Rewrite `WST/test_tracking.py` against `AsyncMock(spec=LoopLifecycle)` first. No evidence (spec Clarifications 2026-10-26).
- [x] T019 [L:callers] [BE] [US2] `WS/agents/tools.py::track_loop` gains `session_id: Injected[str | None] = None` and passes it to the tracker; schema unchanged for the model. Update `WST/test_track_loop_tool.py` and `WST/test_track_loop_undo_payload.py` (assert `session_id` is hidden from the schema).

**Checkpoint**: every event exists and is tested; callers use them. The inflow still uses the old path until US3.

---

## Phase 4: User Story 3 — An admitted loop is committed by one method with one decision (Priority: P2)

**Goal**: one `CommitDecision` vocabulary, one `LoopInflow.commit`, no closure, no remap.

**Independent Test**: `PG/test_loop_commit_pg.py` — `commit` with each decision against test-pg and a fake title writer; `test_commit_path_arity`.

### Tests for User Story 3

- [x] T020 [P] [L:inflow] [BE] [US3] Write `WST/test_admission.py` cases first (fail on today's code): `commit(hold)` writes nothing; `commit(fallback)` runs the 109 gate once and commits its decision (US3-2); no title → `no_title`; `resolve` with no live match → `no_match`, not an error; a suspected create blocked by a dropped fingerprint → `dismissed`; a live non-suspected match → `lifecycle.note_evidence`; any exception → `error`, never raised; a `create_declared` whose evidence does not exist (the seam's existence check fails) → `error` and no loop; `test_commit_path_arity`: every function and method `commit` reaches in `admission.py`, `extraction.py` and `corroboration.py` (listed by name in the test) has at most 8 parameters (SC-003).

### Implementation for User Story 3

- [x] T021 [P] [L:inflow] [BE] [US3] `WS/loop_judge.py`: `decide` returns `CommitDecision` with a `GateKind`; delete `DecisionKind` and `LoopGateDecision`. `WST/test_loop_judge.py` asserts over every contract row that `decide` never returns `create_declared`.
- [x] T022 [P] [L:inflow] [BE] [US3] `WS/commitment_judge.py`: in `OutcomeKind`, `resolve_loop` → `resolve`, `create_loop_declared` → `create_declared`, `create_loop_suspected` → `create_suspected`, and the matching `return IntakeOutcome(...)` lines in `decide()`; nothing else in the file. Update `WST/test_commitment_judge.py`, `WST/test_commitment_labels.py`, `WST/commitment_fixtures.py`, `WST/test_commitment_calibration_scoring.py` and `WST/test_commitment_calibration_sets.py` if they name the old strings.
- [x] T023 [P] [L:inflow] [BE] [US3] `eval/calibration/commitment_intake.py`: the kind literals only (`CREATES`, `WRITES`, lines ~335-336 and ~879). Run `make calibrate-commitment-intake ARGS=--check-sets` and `make calibrate-loop-gate ARGS=--check-sets` (offline); `loop_gate.py` and `commitment_intake_baseline.py` should need no change.
- [x] T024 [P] [L:inflow] [WEB] [US3] `apps/ze-web/src/widgets/assemble/lib/instruments/judgments.ts:84-86`: keys `resolve`, `create_declared`, `create_suspected` with the same three sentences; update `judgments.test.ts` rows first. `make test-web` and `make typecheck-web` green.
- [x] T025 [L:inflow] [BE] [US3] `WS/extraction.py`: add `decide_with_109_gate(text, llm_client, model) -> CommitDecision` mapping `_ExtractionGateResult` (research R6; failed gate → `hold`/`gate_failed`), with `WST/test_extraction.py` cases for each mapping. Keep `_run_extraction_gate`, `_SYSTEM_PROMPT`, `_ExtractionGateResult`, `_loads_json`, `write_loop_title`, `resolve_entities`, `_whole_days` and `_existence_checkers` by name.
- [x] T026 [L:inflow] [BE] [US3] `WS/corroboration.py`: replace `corroborate_match` / `_corroborate` with `Corroborator` and `MatchInput` (contracts/inflow-commit.md); its effects call `lifecycle.note_evidence`, `lifecycle.corroborate`, `lifecycle.promote`; keep `_judge`, the surface-config block, `is_independent` and `corroborated_confidence`; `PROMOTED_WINDOW_DAYS` reads `DeclaredStamp.DEFAULT_WINDOW_DAYS`. Rewrite `WST/test_corroboration.py` and `WST/test_corroboration_flow.py` against `AsyncMock(spec=LoopLifecycle)`.
- [x] T027 [L:inflow] [BE] [US3] `WS/admission.py`: `LoopInflow.__init__` per contract (adds `lifecycle`, drops `memory_store`, `collision_store`, `nli_client`); `finish(...)` builds the full `LoopAdmission` (`text`, `inflow`, `source`) and attaches nothing; add `commit(...)` per the contract's decision table, with helpers taking one frozen `_Commit` value; `extract` calls `self.commit`. Delete `commit_for`. In `WS/extraction.py` delete `propose_loop_candidates`, `_commit_admitted`, `_create_declared_loop`, `_create_suspected_loop`, `_close_matching_loop`, `_match_existing`, `_corroborate_match`, `_record_origin`, `_link_evidence_and_entities` and the unreachable `user_declared` branch. `WS/inflow.py`: `make_loop_inflow_from_parts` / `make_loop_extractor_from_parts` / `make_loop_extractor` take `lifecycle` and drop the three moved dependencies. Update `WST/test_loop_evidence_plumbing.py` and `WST/test_graph_integration.py`. T020 green.
- [x] T028 [L:inflow] [BE] [US3] `WS/intake.py`: constructor takes `lifecycle`; `loop_inflow` read-only property; `_apply` builds `CommitDecision(outcome.kind, outcome.reason, outcome.consumed)` for the three loop kinds; `_fallback` uses `CommitDecision("fallback", reason)`; `_loop_admission` passes `source` to `finish` (no mutation after); `_link_one` calls `lifecycle.link`; delete `_LOOP_KIND`. Update `WST/test_intake.py` first.
- [x] T029 [L:inflow] [BE] [US3] `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (loop-commit hunk ~197-200 and `_commit_with_episode` ~292-300 only): read `configurable["loop_commit"]`, skip `hold`, pass `decision`, `text`, `inflow`, `source` from the admission and the episode as evidence (contracts/inflow-commit.md). Update `core/engine/ze-core/tests/orchestration/test_loop_admission_node.py` first, and only the fakes that set `admission.commit` in `core/engine/ze-core/tests/orchestration/nodes/test_memory_judgments.py`. `make test-core` green.
- [x] T030 [L:inflow] [BE] [US3] Write `PG/test_loop_commit_pg.py` (after T016 is merged): `LoopInflow.commit` with each decision, a fake title writer and System One off produces the expected rows (US3-1: one suspected loop with evidence and an origin source); the SC-005 replay from research R12 (30 simulated days, both sweeps each day, no dropped or expired loop with evidence comes back; the evidence-less expired loop is created again); a `create_declared` with an episode id that does not exist ends as `CommitResult("error")` with no row (FR-013).
- [x] T031 [L:inflow] [BE] [US3] Move `PG/test_loop_evidence.py` and `PG/test_loop_resolve_pg.py` from `propose_loop_candidates` to `LoopInflow.commit` with an explicit `CommitDecision`; behavior assertions unchanged.
- [ ] T032 [L:inflow] [BE] [US3] Rebase the `inflow` branch onto the floor branch once 202 has landed on `main` and the floor branch is rebased (plan.md "Coordination with 202"). Re-run `make test-worldstate`, `make test-core` and the two `--check-sets` runs.

**Checkpoint**: all three stories work; the old store writes are unused.

---

## Phase 5: Integration and cleanup (lead)

- [x] T033 [L:lead] [BE] After merging `callers`: `apps/ze-api/ze_api/wiring/container.py` builds `LoopTracker(loop_store=…, lifecycle=worldstate.lifecycle, graph_store=…, entity_resolver=…, embedder=…)`. `make test` green.
- [x] T034 [L:lead] [BE] After merging `inflow`: `apps/ze-api/ze_api/wiring/hooks.py` (`build_commitment_intake`, `wire_ingestion_loop_extractor`) passes `lifecycle` to `CommitmentIntake` and the inflow builders; `container.py::_build_config` sets `configurable["loop_commit"] = self.commitment_intake.loop_inflow.commit` inside the existing `if self.commitment_intake is not None:` block. Add a container test that the key is set when the intake is.
- [ ] T035 [L:lead] [BE] Shrink `WS/store.py` to the reads listed in contracts/lifecycle-events.md: delete every write method, `_ALLOWED_TRANSITIONS`, `_USER_ASKED_TRANSITIONS`, `_CONFIDENCE_STAMP` and the `LoopStore` protocol's write members (FR-007). Update `WST/test_store.py` and `WST/test_store_list_since.py`.
- [ ] T036 [L:lead] [BE] Delete `types.DECLARED_CONFIDENCE`, `drift.DEFAULT_DRIFT_WINDOW_DAYS` and `drift.compute_drift_deadline`. First `grep -rn "DECLARED_CONFIDENCE\|DEFAULT_DRIFT_WINDOW_DAYS\|compute_drift_deadline" core apps eval --include='*.py'`: any reader left in another lane's file (e.g. `WST/test_confirm_loop_tool.py`, `WST/test_corroboration.py`) goes back to that lane before this task. Update the lead-owned readers (`WST/test_drift.py`, `PG/test_loop_confirmation_pg.py`) to `DeclaredStamp`.
- [ ] T037 [L:lead] [BE] Delete `LoopAdmission.commit` in `WS/types.py`; make `source` a plain constructor field (already set at construction since T028). Apply 202's `judgment` field shape if the floor branch was rebased.
- [ ] T038 [L:lead] [BE] Add `WST/test_lifecycle_invariants.py`: the stamp-once check (`0.9` and the declared-stamp fragment occur only in `WS/lifecycle/rules.py`, SC-002) and the FR-007/FR-008/FR-009 static checks from quickstart.md §3 as assertions over the source files.
- [ ] T039 [L:lead] [PLATFORM] Gates: `make test-worldstate`, `make test-core`, `make test`, `make test-priority`, `make test-py`, `make test-pg`, `make test-web`, `make typecheck-web`, `make lint`, the two `--check-sets` runs; and `git diff main...HEAD --stat -- core/cognition/ze-correlation` is empty (FR-011). Record results in the floor Handoffs note.

---

## Phase 6: Documentation

- [ ] T040 [P] [L:docs] [DOCS] Update the public docs from the finished diff (doc-style skill rules): `core/cognition/ze-worldstate/README.md` (lifecycle package, events table, the store is reads only, `review.py`/`decay.py` gone, `LoopInflow.commit`, module table rows for `lifecycle/`, `decision.py`, `admission.py`, `extraction.py`, `corroboration.py`), `docs/system-one.md:75` (corroboration now runs in `corroboration.py`'s `Corroborator`, not "both suspected match paths in `extraction.py`"), `docs/engineering/open-loops-executive-function.md`, `docs/cognitive-architecture.md` and `docs/architecture.md` (check each for store/transition wording and fix what names changed code), `docs/scheduled-jobs.md` (check; job modules unchanged).
- [ ] T041 [L:docs] [DOCS] Indexes: `AGENTS.md` layout tree for `ze-worldstate` (add `lifecycle/` and `decision.py`, drop `review.py` and `decay.py`, reword `admission.py`, `extraction.py`, `corroboration.py`, `store.py`) and the phase table row for 203 (Implemented, one-paragraph summary in the table's style); `specs/README.md` 203 row Status → `✅ Implemented (no migration)`; `spec.md` Status line → Implemented.
- [ ] T042 [L:docs] [DOCS] Coverage check: `git diff main...HEAD --stat -- docs/ AGENTS.md specs/README.md '*README.md'`. Confirm every file in T040–T041 appears or is recorded as "checked, no change". List any public doc that names a changed symbol but was not updated, with a reason: `grep -rnE "LoopStore\.|stamp_declared|propose_loop_candidates|commit_for|LoopGateDecision|review\.py|decay\.py|cascade_from_evidence|create_loop_declared|resolve_loop" docs/ README.md */*/README.md */*/*/README.md`.

---

## Dependencies & Execution Order

- **Phase 1 (T001–T006)** blocks everything.
- **US1**: T007 → T008 → T009 (lead). T010–T012 (callers) start after Phase 1 and test against mocks; they need T008 only for the final pg run.
- **US2**: T013 → T014–T016 → T017 (lead). T018–T019 (callers) after Phase 1.
- **US3** (inflow): T020–T029 after Phase 1, in parallel with US1/US2; T030–T031 after T016; T032 after 202 lands.
- **Phase 5**: T033 after `callers` merges; T034 after `inflow` merges; T035–T038 after both; T039 last.
- **Phase 6**: after T039.

### Lane view

| Lane | Tasks | Order |
|---|---|---|
| lead | T001–T009, T013–T017, T033–T039 | contract → US1 events → US2 events → integration → cleanup → gates |
| callers | T010–T012, T018–T019 | after contract |
| inflow | T020–T032 | after contract; T030–T031 after T016; T032 after 202 lands |
| docs | T040–T042 | after T039 |

## Parallel Examples

```text
# After the contract merges, three agents at once:
lead:    T007 → T008            (US1 event bodies, pg)
callers: T010, T011 in parallel (REST and tools onto the lifecycle)
inflow:  T020, T021, T022, T023, T024 in parallel (tests, vocabulary, calibration literals, web map)
```

## Implementation Strategy

- **MVP**: Phase 1 + US1 (T001–T012). Drop, expire, confirm, close, decay and drift are atomic and the fingerprint bug is fixed; the inflow still uses the old path.
- **Then** US2 (one stamp, both creates aligned), then US3 (commit path), then integration and the store shrink.
- Every task ends with its package's `make test-<pkg>` and `make lint` green.

## Notes

- Commit each task with its checkbox ticked in the same commit (AGENTS.md, Learned User Preferences).
