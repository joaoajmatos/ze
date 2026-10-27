# Implementation Plan: Open-Loop Lifecycle

**Branch**: `203-open-loop-lifecycle` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/203-open-loop-lifecycle/spec.md`

## Summary

One lifecycle module, `ze_worldstate/lifecycle/`, becomes the only way to change an open loop. Its interface is the fourteen domain events (create suspected, create declared, confirm, track, note evidence, corroborate, promote, resolve, close, drop, expire, link, decay, drift). Each event is one transaction guarded by the loop's state, and the event × state rules and the declared stamp live in one pure table. `PostgresLoopStore` shrinks to reads. On the commit side, `LoopInflow.commit(decision, *, text, inflow, evidence, source)` replaces the `commit_for` closure and the 16-parameter threading, and one `CommitDecision` vocabulary replaces the `IntakeOutcome → LoopGateDecision` string remap. Every event gets a real-Postgres test, including a forced failure of its second write. No migration. Design decisions: [research.md](research.md); rules: [data-model.md](data-model.md); interfaces: [contracts/](contracts/).

## Technical Context

**Language/Version**: Python 3.12; TypeScript (one ze-web map file)

**Primary Dependencies**: asyncpg (transactions), the contribution seam (`ze_collision.detect.submit_and_detect_collisions`), System One judges (unchanged; 202 reshapes their carriers)

**Storage**: PostgreSQL, existing tables `open_loops`, `open_loop_sources`, `memory_relationships`. No schema change (research R13). Next free worldstate revision on `main` would be `zw007`; not used.

**Testing**: pytest unit suites (`make test-worldstate`, `make test-core`, `make test`), real-Postgres suite (`make test-pg`, `pytest.mark.pg`), vitest (`make test-web`)

**Target Platform**: Ze backend (local, self-hosted)

**Project Type**: monorepo backend package refactor with one web string map

**Performance Goals**: no regression; each event is one round trip or one short transaction

**Constraints**: ze-core never imports ze-worldstate (write_memory reads the admission by attribute); plugins untouched; 202 lands first and this phase rebases onto it

**Scale/Scope**: ~13 worldstate modules, 3 ze-api wiring files, 1 ze-core hunk, 1 web file, ~25 test modules

**Doctrine function**: executive function. Open loops are Ze's model of the user's unfinished business (`specs/arch/executive-function.md`, `ze-doctrine.md`).

## Constitution Check

*Assessed before research and again after design. All PASS.*

- **I. Spec-First Development**: PASS. spec.md (clarified), this plan, research, data model and contracts precede code.
- **II. Single-User Model**: PASS. No user scoping added.
- **III. Layered Package Architecture**: PASS. All new code is in `core/cognition/ze-worldstate`. ze-core reads the admission by attribute and gets the commit through `configurable`, never importing ze-worldstate. No plugin changes. No new package dependency (`ze-worldstate` already depends on `ze-agents`, `ze-collision`, `ze-memory`, `ze-plugin`).
- **IV. Typed, Explicit Python**: PASS. Frozen dataclasses in `decision.py` and `lifecycle/events.py`; typed `ZeError` subclasses (`InvalidLoopTransitionError`, `LoopNotFoundError`) reused; constructor injection; `get_logger`.
- **V. Test Discipline**: PASS. Unit tests mock `LoopLifecycle`, never a pool, for callers; the lifecycle's own behavior is tested against real Postgres (`make test-pg`), which the constitution's unit-test rule allows because those tests are `pg`-marked and outside `test-py` (AGENTS.md, Testing).
- **VI. Explicit Persistence**: PASS. No migration; raw SQL only.
- **VII. One LLM Gateway, Local Embeddings**: PASS. Title writer and 109 gate unchanged.
- **VIII. Pre-v1 Hard Cuts**: PASS. Store write methods, `review.py`, `decay.py`, `commit_for`, `propose_loop_candidates`, `LoopGateDecision` and `_LOOP_KIND` are deleted, not wrapped. Old stored traces show the raw intake kind (no alias).

## Blast radius (graphify `affected --depth 2`, plus grep)

Callers by package, counted on 2026-10-26 after `graphify update .`:

| Symbol | Production callers | Test callers |
|---|---|---|
| `PostgresLoopStore` write methods | ze-worldstate: `review.py`, `decay.py`, `tracking.py`, `corroboration.py`, `extraction.py`, `intake.py`, `jobs/drift_sweep.py`, `jobs/stale_suspicion.py` (26 calls + 3 `create`) | ze-api `tests/pg` (62 calls in 14 files), ze-worldstate tests (32) |
| `review.confirm_loop / close_loop / drop_loop` | `ze_worldstate/rest.py`, `ze_worldstate/agents/tools.py` | ze-worldstate `test_review.py`, `test_rest.py`, `test_confirm_loop_tool.py`; ze-api `tests/api/test_loops_route.py` |
| `cascade_from_evidence` | `apps/ze-api/ze_api/wiring/hooks.py:43-48` | ze-worldstate `test_decay.py` (6), ze-api (1) |
| `DriftSweepJob`, `StaleSuspicionJob` | `ze_worldstate/bootstrap.py`, ze-api `wiring/jobs.py` (4) | ze-worldstate `tests/jobs/` (13), ze-api pg (9) |
| `LoopTracker` | `ze_worldstate/agents/{agent,tools}.py`, ze-api `wiring/{agents,container}.py` (8) | ze-worldstate (21), ze-api (16) |
| `corroborate_match` | `extraction.py` (3) | ze-worldstate `test_corroboration*.py` (15) |
| `propose_loop_candidates`, `LoopInflow.commit_for` | `admission.py` | ze-api pg `test_loop_evidence.py`, `test_loop_resolve_pg.py` (9); ze-worldstate (51) |
| `LoopGateDecision` | ze-worldstate (27), `apps/ze-api` (1) | ze-worldstate (55), ze-api (10) |
| `CommitmentIntake` | ze-api `wiring/{hooks,container}.py` | ze-worldstate (69) |
| `_commit_with_episode`, `LoopAdmission.commit` | ze-core `orchestration/nodes/memory.py` | ze-core `tests/orchestration/nodes/test_memory_judgments.py`, `tests/orchestration/test_loop_admission_node.py` (35) |
| `IntakeOutcome` loop kinds | `commitment_judge.py`, `intake.py` | `eval/calibration/commitment_intake.py`; ze-web `widgets/assemble/lib/instruments/judgments.ts` (+ test) |
| `extraction._run_extraction_gate`, `_SYSTEM_PROMPT`, `_ExtractionGateResult`, `_loads_json` | — | `eval/calibration/loop_gate.py` imports them: names kept (research R7) |
| `LoopStore` (reads only) | ze-priority `view.py`, `compose/composer.py`; `surfacing.py`; `matching.py`; ze-api router and `deps.py` | unchanged signatures for reads |

graphify does not resolve `LoopStore` (a Protocol), the three `review` function names (duplicated by the tool names) or `IntakeOutcome`; grep covered them. It also missed ze-priority's read imports and the calibration imports.

## Coordination with 202 (judgment surface, floor 202, architect Cairn)

Agreed 2026-10-26 (Handoffs note "203 Handoffs"; Cairn records the same in 202's plan under "Coordination with 203"). The Maestro confirmed: **202 lands first; 203 owns FR-009 (`loop_judge.DecisionKind` and the commit vocabulary) entirely; 203 rebases onto 202.**

| File | 202 owns | 203 owns |
|---|---|---|
| `ze_worldstate/admission.py` | `LoopInflow._judge` body (one call to the shared surface module), `finish`'s `judgment` parameter, `_log` reading the record | `commit_for` (deleted), the commit attachment in `finish`, the new `commit` method and its helpers, the constructor's dependency list |
| `ze_worldstate/types.py` | `LoopAdmission.judgment` (one `Judgment` record replacing five fields) | `LoopAdmission.decision` type, `text` / `inflow` / `source` as constructor fields, `commit` removed; `DECLARED_CONFIDENCE` removed; the `loop_judge` import removed |
| `ze_worldstate/intake.py` | `IntakeAdmission` judgment fields; the judging block in `admit()`; `_fallback`'s record building | `_LOOP_KIND` (deleted), `_apply`'s loop branch, `_loop_admission`, `_link_one`, the `loop_inflow` property, the `lifecycle` constructor parameter |
| `ze_worldstate/commitment_judge.py` | config dataclass + surface parser (moved to the shared surface) | the three loop kinds in `OutcomeKind` and the matching `return` statements in `decide()` |
| `ze_worldstate/loop_judge.py` | config dataclass + surface parser | `DecisionKind` / `LoopGateDecision` (deleted), `decide`'s return type (`CommitDecision`, gate subset) |
| `ze_worldstate/corroboration.py` | `_judge` and the surface-config block in `_corroborate` | the effect side and the signature (`Corroborator`, research R10); 202's lines move into the method verbatim |
| `ze_core/orchestration/nodes/memory.py` | the judgment-row hunk (~160-193, including deleting the dead fact_judge branch) | the loop-commit hunk (~197-200) and `_commit_with_episode` (~292-300) |
| `ze-core tests/orchestration/nodes/test_memory_judgments.py` | judgment-row tests | only the fakes that set `admission.commit` |
| `eval/calibration/*` | everything | only the kind-string literals in `commitment_intake.py` |

**Rebase rule**: before review, lane `inflow` rebases its branch onto the floor branch after the floor branch is rebased onto `main` with 202 landed. Where 202 changed a line 203 also deletes, take 202's shape and then apply 203's change.

## Other floors with nearby lines

| Floor | Shared file | 203's hunk | Rule |
|---|---|---|---|
| 201 typed turn services (Specified) | `apps/ze-api/ze_api/wiring/container.py`, `api/deps.py`, the `*Stack`s | one `configurable["loop_commit"]` line inside the same `if self.commitment_intake is not None:` block as `commitment_intake`; `LoopTracker(...)` arguments; `get_loop_lifecycle`; `WorldstateStack.lifecycle` | whichever lands second carries the other's lines; 201 moves `loop_commit` into its services object |
| 204 push bar and cooldowns (Ready) | `ze_worldstate/bootstrap.py` (204's `bar` lane: `LoopPushSettings`, `build_loop_surfacer`); `apps/ze-api/ze_api/wiring/container.py` (204's `lead`); `wiring/hooks.py` | `build_worldstate_stack` and `WorldstateStack.lifecycle`; the `loop_commit` key and `LoopTracker(...)` in `container.py`; `install_contradiction_hook`, `wire_collision_detection`, `build_commitment_intake` in `hooks.py` | hunks are disjoint; whichever lands second rebases. 204's R14 says it shares no file with 203: the Maestro relays this row to 204's architect so 204's plan lists it too |
| 200 agent context derivation (Specified) | `apps/ze-api/ze_api/wiring/container.py` | as above | disjoint hunks; rebase note in both plans (relayed by the Maestro) |
| 212 contribution submitter (Specified, depends on 203) | the loop submit sites | they move from `extraction.py` / `tracking.py` to `lifecycle/events.py` | 212's spec must be re-pointed when it is planned; recorded here for its architect |

## Project Structure

### Documentation (this feature)

```text
specs/phases/203-open-loop-lifecycle/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── lifecycle-events.md
│   └── inflow-commit.md
├── checklists/
└── tasks.md
```

### Source Code

```text
core/cognition/ze-worldstate/ze_worldstate/
├── lifecycle/            # NEW: __init__.py, rules.py (pure), events.py (LoopLifecycle)
├── decision.py           # NEW: CommitDecision, CommitResult, CommitKind, GateKind
├── store.py              # reads only
├── types.py              # LoopAdmission fields; DECLARED_CONFIDENCE removed
├── drift.py              # rationales only; deadline helper and window constant removed
├── admission.py          # LoopInflow.commit
├── extraction.py         # 109 gate (+ decide_with_109_gate), title writer, entity resolution
├── corroboration.py      # Corroborator + pure rules
├── intake.py, commitment_judge.py, loop_judge.py, inflow.py, tracking.py, rest.py, bootstrap.py
├── agents/tools.py
├── jobs/drift_sweep.py, jobs/stale_suspicion.py
├── review.py, decay.py   # DELETED
core/engine/ze-core/ze_core/orchestration/nodes/memory.py   # loop-commit hunk
apps/ze-api/ze_api/wiring/{container,hooks}.py, api/deps.py, api/v0/loops/router.py
apps/ze-api/tests/pg/     # conftest fault trigger, _builders, lifecycle + commit pg tests
apps/ze-web/src/widgets/assemble/lib/instruments/judgments.ts (+ test)
eval/calibration/commitment_intake.py   # kind literals only
```

**Structure Decision**: everything stays in `ze-worldstate`, the package that owns the tables. The lifecycle is a sub-package so its pure rules can be tested without importing SQL.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first, T001–T006): the files every lane codes against.

- `ze_worldstate/lifecycle/rules.py` complete (pure, with the table test), `lifecycle/events.py` with every signature, value type and docstring from [contracts/lifecycle-events.md](contracts/lifecycle-events.md) and bodies raising `NotImplementedError`, `lifecycle/__init__.py`.
- `ze_worldstate/decision.py` complete ([contracts/inflow-commit.md](contracts/inflow-commit.md)).
- `ze_worldstate/types.py`: `LoopAdmission.decision` becomes `CommitDecision`; `text` and `inflow` added with defaults. `commit` and `DECLARED_CONFIDENCE` stay until the cleanup tasks (T036–T037) so the build stays green while lanes move.
- `bootstrap.py`: `LoopLifecycle` built and in `deps`; `WorldstateStack.lifecycle`.
- `bootstrap.py` / `hooks.py` / `api/deps.py`: the lifecycle built, injected and reachable from REST.
- `apps/ze-api/tests/pg/conftest.py`: the `ze_test_faults` trigger (research R9); `_builders.make_loop` seeding by SQL.

The store's old write methods stay until T035: removing them first would break every caller before its lane has moved.

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `ze_worldstate/lifecycle/` (new), `decision.py` (new), `store.py`, `types.py`, `drift.py`, `errors.py`, `fingerprint.py`, `bootstrap.py`, `jobs/{drift_sweep,stale_suspicion}.py`, `decay.py` (deleted); `apps/ze-api/ze_api/wiring/{container,hooks}.py`, `apps/ze-api/ze_api/api/deps.py`; `apps/ze-api/tests/pg/` except the two files lane `inflow` owns; ze-worldstate tests `test_lifecycle_rules.py` (new), `test_store.py`, `test_store_list_since.py`, `test_drift.py`, `test_fingerprint.py`, `test_claim_kind.py`, `test_bootstrap.py`, `test_decay.py` (deleted), `tests/jobs/`, `test_lifecycle_invariants.py` (new), `test_decision.py` (new); ze-api `tests/agents/test_bootstrap.py`; merges, integration wiring and final gates | T001–T009, T013–T017, T033–T039 | - | floor reviewer (Maestro assigns) |
| callers | Sonnet ENG | `ze_worldstate/{tracking,rest}.py`, `ze_worldstate/agents/tools.py`, `ze_worldstate/review.py` (deleted), `apps/ze-api/ze_api/api/v0/loops/router.py`; tests `test_tracking.py`, `test_track_loop_tool.py`, `test_track_loop_undo_payload.py`, `test_confirm_loop_tool.py`, `test_loop_agent_cancel.py`, `test_review.py` (deleted), `test_rest.py`, `test_rest_evidence_summaries.py`, ze-api `tests/api/test_loops_route.py`, `tests/test_undo_payload_contract.py`, `tests/test_tool_asks_first_audit.py` | T010–T012, T018–T019 | contract step | floor reviewer (Maestro assigns) |
| inflow | Sonnet ENG | `ze_worldstate/{admission,intake,extraction,corroboration,loop_judge,commitment_judge,inflow}.py`; `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (loop-commit hunk only); `eval/calibration/commitment_intake.py` (kind literals only); `apps/ze-web/src/widgets/assemble/lib/instruments/judgments.ts` and `judgments.test.ts`; tests `test_admission.py`, `test_intake.py`, `test_extraction.py`, `test_commitment_judge.py`, `test_commitment_labels.py`, `test_loop_judge.py`, `test_commitment_calibration_scoring.py`, `test_commitment_calibration_sets.py`, `test_corroboration.py`, `test_corroboration_flow.py`, `test_loop_evidence_plumbing.py`, `test_graph_integration.py`, `commitment_fixtures.py`; ze-core `tests/orchestration/test_loop_admission_node.py` and the `admission.commit` fakes in `tests/orchestration/nodes/test_memory_judgments.py`; ze-api pg `test_loop_commit_pg.py` (new), `test_loop_evidence.py`, `test_loop_resolve_pg.py` | T020–T032 | contract step (pg tasks T030–T031 after T016; T032 after 202 lands) | floor reviewer (Maestro assigns) |
| docs | Haiku DOCS | `core/cognition/ze-worldstate/README.md`, `docs/system-one.md`, `docs/engineering/open-loops-executive-function.md`, `docs/cognitive-architecture.md`, `docs/architecture.md`, `docs/scheduled-jobs.md` (check), `AGENTS.md`, `specs/README.md` (203 row), `spec.md` (Status line) | T040–T042 | T039 | floor reviewer (Maestro assigns) |

**Rules**:

- **One lane per file.** A lane that needs a change in another lane's file asks that lane (or `lead`).
- **Contract first.** `callers` and `inflow` start when T001–T006 are merged into the floor branch. They test against `AsyncMock(spec=LoopLifecycle)` until `lead` lands the event bodies (T008, T014–T016).
- **Integration wiring belongs to `lead`.** `callers` changes the `LoopTracker` constructor and `inflow` changes the `LoopInflow`, `CommitmentIntake` and `make_loop_*_from_parts` constructors in their own files; `lead` updates their construction sites (`wiring/container.py`, `wiring/hooks.py`) right after merging each lane (T033, T034). Until then the lane's own tests construct the classes directly.
- **pg tests that need real events** (lane `inflow`'s T030–T031) start after T016.
- **202 rebase.** Lane `inflow` owns every 202-shared hunk on this floor and does the rebase onto 202 (see "Coordination with 202"). Lane `lead` owns `types.py` and applies 202's `LoopAdmission.judgment` change on rebase.
- **Merge order.** `lead` merges `callers`, then `inflow`, then runs cleanup and the final gates (T035–T039). `docs` runs last from the finished diff.
- **No JR lane.** The work is cross-module refactoring with design judgment at each call site; nothing is specified tightly enough for Haiku.
- **Branches.** Each lane works on a sub-branch of `203-open-loop-lifecycle` in its own worktree. Each lane is reviewed as it finishes.

## Complexity Tracking

No violations.
