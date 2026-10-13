# Implementation Plan: Executive Repair

**Branch**: `170-executive-repair` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/170-executive-repair/spec.md` (clarified 2026-10-12). Governing: [`specs/arch/executive-function.md`](../../arch/executive-function.md) F1, F3, F9, F13 and §3.2.

## Summary

Four verified defects and a test gap, one phase:

1. **Drift (F1).** The sweep selects on the deadline alone. A new `record_corroboration` store method is the only thing that moves a deadline later. No column, no migration.
2. **Stuck goals (F3).** `list_stuck` returns one row per goal from the earliest *fired* open gate.
3. **Evidence (F9).** `write_episode` returns its id; the conversation commit, the messenger processor and the ingestion sink pass source evidence to the loop commit; the declared path dedups and uses existence checkers; push grounding checks the loop *title*; fingerprint semantics are documented and tested.
4. **Visibility (F13).** The snapshot response carries `sources_failed`, accepts `relationship`, and the web page shows what is missing.
5. **Hygiene.** Wire `worldstate.push.*` and `correlation.push.enabled/dry_run`; delete the dead modules and keys.
6. **Harness.** `apps/ze-api/tests/pg/` with `make test-pg`, opt-in, throwaway `pgvector` container, real migrations.

Nothing in System One, the gate questions, bars, ranking order or the contribution seam changes.

## Technical Context

**Language/Version**: Python 3.11+, TypeScript (one hook, one widget, generated client).

**Primary Dependencies**: Existing only. No `testcontainers`; the harness shells out to `docker`. No new package edge: `ze-core` already depends on `ze-plugin` (for `EvidenceRef`); `ze-messenger` imports `EvidenceRef` from `ze_sdk.contribution`; `ze-ingestion` already imports it.

**Storage**: No migration. SQL changes in `PostgresLoopStore.list_drift_candidates`, new `record_corroboration`, `PostgresGoalStore.list_stuck`, one `memory_episodes` select in `ze_worldstate/rest.py`.

**Testing**: pytest unit suites with fakes for fast feedback; `apps/ze-api/tests/pg/` for real-row regression and the two acceptance runs; vitest for the web notice. Live System One and OpenRouter are never called.

**Target Platform**: Background jobs (`DriftSweepJob`, `StuckGoalJob`, `AttentionArbitrationJob`), the `write_memory` node, `ze-api` REST, `ze-web`.

**Performance Goals**: No new request on the turn path. The commit awaits the episode task in the background. `list_stuck` adds `DISTINCT ON` over a small table.

**Constraints**:
- Dependency graph: `ze_core` stays unaware of `ze_worldstate` (duck-typed commit). Plugins import `EvidenceRef` from `ze_sdk.contribution`, never `ze_plugin` or `ze_worldstate`.
- Pre-v1 hard cuts: dead modules deleted in the same phase; the REST shape changes at its single consumer; the extractor callable signature changes at all three owners.
- Phase 169 is not on `main` yet: 170 edits no `transition` or `stamp_declared` code.
- OpenAPI: the changed route keeps `response_model`, `summary`, `description`.

**Scale/Scope**: Single user; tens of loops.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First Development | PASS — spec, research and contracts precede code; ADR note `executive-function.md` governs |
| II. Single-User Model | PASS |
| III. Layered Package Architecture | PASS — `EvidenceRef` via `ze_sdk` for plugins; node duck-types the admission; the harness sits in ze-api, which already depends on every package under test |
| IV. Typed, Explicit Python | PASS — dataclass `PrioritySnapshotResult`; Pydantic only in `schemas.py`; `get_logger`; typed errors in domain code (`PgHarnessError(RuntimeError)` lives in test support only) |
| V. Test Discipline | PASS — fail-first regression per finding; real DB only in the opt-in marker; no live model call |
| VI. Explicit Persistence | PASS — no schema change; SQL stays raw in stores |
| VII. One LLM Gateway, Local Embeddings | PASS — untouched |
| VIII. Pre-v1 Hard Cuts | PASS — dead code deleted, response shape and extractor signature changed in one step; no compat shim, no dual shape |

**Post-design re-check**: R1 chose "move the deadline" over a new column to avoid a migration and a second clock. R5 keeps the grounding gate meaningful instead of letting evidence silently block every push. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/170-executive-repair/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── drift-and-corroboration.md
│   ├── stuck-goals.md
│   ├── loop-evidence.md
│   ├── priority-snapshot.md
│   └── pg-harness.md
├── checklists/requirements.md
├── spec.md
└── tasks.md
```

### Source Code (touch map)

```text
core/cognition/ze-worldstate/ze_worldstate/
├── store.py            # list_drift_candidates, record_corroboration (+Protocol)
├── drift.py            # is_drift_eligible, compose_absence_rationale
├── jobs/drift_sweep.py # use store filter, catch InvalidLoopTransitionError, drop is_stale
├── extraction.py       # evidence plumbing, declared dedup, checkers helper, corroboration calls
├── admission.py        # commit(evidence), extract(evidence)
├── types.py            # LoopAdmission.commit type; delete DriftingLoopMention
├── inflow.py           # extractor callables accept evidence
├── surfacing.py        # grounding on title; delete inline_candidates
├── rest.py             # episode summary for messenger
└── bootstrap.py        # (read worldstate.push cfg helper)
core/cognition/ze-memory/ze_memory/
├── store.py, retriever.py   # write_episode -> UUID | None
└── surfacing.py             # DELETE
core/automation/ze-automation/ze_automation/goals/postgres.py   # list_stuck
core/arbitration/ze-priority/ze_priority/
├── types.py, rest.py        # PrioritySnapshotResult
├── arbitration.py           # loop push settings
└── learning_context.py      # DELETE
core/cognition/ze-correlation/ze_correlation/push.py            # enabled / dry_run
core/engine/ze-core/ze_core/orchestration/nodes/memory.py       # commit with episode ref
plugins/ze-messenger/ze_messenger/inbound/processor.py          # episode id -> extractor
core/ops/ze-ingestion/ze_ingestion/sink.py                      # evidence -> extractor
plugins/ze-calendar/ze_calendar/jobs/calendar_reminder.py       # type only, debug log
apps/ze-api/
├── ze_api/api/schemas.py, api/routes/priority.py, compose.py
├── config/config.yaml
├── pyproject.toml (marker)
└── tests/pg/            # NEW harness and PG tests
apps/ze-web/src/{entities/priority-item, widgets/priority-snapshot}
packages/ze-client/src/generated/   # make codegen
Makefile, docs/, READMEs, AGENTS.md, specs/README.md
```

## Impact analysis (graphify `affected`, run at spec time; implementers re-run before each signature change)

| Symbol changed | Callers found | Action |
|---|---|---|
| `MemoryStore.write_episode` return type | `ze_core/.../nodes/memory.py:116`, `ze_messenger/inbound/processor.py:126`; impl `retriever.py:301`; Protocol `store.py:57` | Return `UUID | None`; two callers updated; test doubles in `ze-memory`, `ze-core`, `ze-messenger` tests updated |
| `LoopAdmission.commit` signature | `nodes/memory.py` (calls `commit()`), `admission.py`, `types.py`; tests `test_admission.py`, `test_loop_admission_node.py` | Takes evidence; node wrapper passes it |
| `make_loop_extractor_from_parts` / `.extract` | `inflow.py`, `container.py:598,849`; owners `processor.py:106`, `calendar_reminder.py:29`, `sink.py:22` | Add optional `evidence`; update the three type hints and the doubles in plugin tests |
| `LoopStore` (new method, changed SQL) | every `LoopStore` fake in tests (`graphify explain LoopStore`) | Add `record_corroboration` to fakes that implement the Protocol |
| `ze_priority.rest.get_snapshot` return type | `routes/priority.py:44`, `_snapshot_row_for` | Update both |
| `PrioritySnapshotItem` / Literal | `schemas.py`, `ze-client` generated, `ze-web` | Regenerate |
| `LoopSurfacer.inline_candidates`, `DriftingLoopMention` | tests only | Delete |
| `SurfacingGate`, `SurfacingConfig` | `test_salience.py` only | Delete |
| `LearningContextAdapter` | its own test only | Delete |

## Implementation order

1. **Harness (US6)** so every later fix has a fail-first real-row test.
2. **Drift (US1)** and **stuck goals (US2)**: independent, each with its PG regression test first.
3. **Evidence (US3)**: `write_episode` return → signatures → node and inflows → declared path → grounding.
4. **Visibility (US4)**: Python → schema → codegen → web.
5. **Hygiene (US5)**.
6. **Acceptance runs, docs, coverage check.**

## Complexity Tracking

| Item | Why it is needed | Simpler alternative rejected because |
|---|---|---|
| New `record_corroboration` method | Only one operation may move a deadline; `link_evidence` runs at birth too | Extending in `link_evidence` overrides short implied windows (R1) |
| Commit takes evidence | The episode id exists only after the turn's background write | Passing the id into `admit()` would block the reply on a write |
| Title grounding | Evidence would turn a vacuous gate into a blocking one (R5) | Leaving rationale grounding blocks all loop pushes |
| Opt-in marker instead of CI-wide Docker | `make test-py` must not need Docker | Always-on Docker tests break the CI gate and offline runs |
