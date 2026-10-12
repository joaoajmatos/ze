# Implementation Plan: Corroboration Promotion

**Branch**: `172-corroboration-promotion` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/172-corroboration-promotion/spec.md` (clarified 2026-10-12; the user answered all six questions). Governing: [`specs/arch/executive-function.md`](../../arch/executive-function.md) D2, [`specs/arch/system-one-models.md`](../../arch/system-one-models.md).

## Summary

When the 168 gate admits a text as a concern and the text matches a `suspected` loop, three steps run:

1. **Independence (code)**: `ze_worldstate/corroboration.py::is_independent` compares the text's `SourceKey` and evidence with the loop's recorded sources and evidence, and with the sources of a matching dropped loop.
2. **Same concern (System One)**: `ze_worldstate/corroboration_judge.py` asks one Noul, `same_concern`, with a single attempt. A pure `decide()` maps the answer to `promote`, `corroborate`, `not_same` or `fallback` against two bars.
3. **Effects (code)**: corroborate links the evidence, writes a source row and raises confidence (noisy-OR, capped at 0.6). Promote does the same, then runs one guarded UPDATE that moves the loop to `active` at 0.7 with a 7-day drift deadline.

A new table, `open_loop_sources` (`zw003`), holds each loop's origin and its counted corroborations, with the score. The REST list and detail expose them, and the loop row on 171's `/loops` page shows "Promoted · seen in: …". `make calibrate-corroboration` calibrates the two bars against an E5-cosine baseline on tuned and held-out pair sets. The surface ships off with null bars. While it is off, the behavior is exactly 170's.

## Technical Context

**Language/Version**: Python 3.11+; TypeScript (ze-web label only).

**Primary Dependencies**: Existing only. `SystemOneClient` types from `ze_agents.system_one`; `loop_judge.build_state` and caps from 168; `drift.DEFAULT_DRIFT_WINDOW_DAYS`; 170's `_existence_checkers` and declared-path dedup. No new package and no new package edge.

**Storage**: Migration `zw003_open_loop_sources` (ze-worldstate `zw` chain, `down_revision = "zw002"`). No change to `open_loops`. `migrate.py` discovers the versions directory by path, so no runner edit. Cairn (170) and Sextant (171) both confirmed that `zw003` is free.

**Testing**: pytest with a fake `LoopStore`, a call-counting fake `SystemOneClient`, a fake embedder and a fake graph store, following `tests/test_admission.py`. Real-Postgres tests use 170's harness (`apps/ze-api/tests/pg/`, `@pytest.mark.pg`, `make test-pg`) and cover the migration, the unique key, the guarded promote and the batched source query. Vitest covers the label. The live calibration runs outside pytest.

**Target Platform**: Background loop commits: the conversation fire-and-forget commit, the email processor task, the calendar job and the ingestion sink.

**Performance Goals**: At most one System One request per independent suspected match. That case is rare: it needs a positive gate, a match, a suspected loop and a new key. Non-independent matches make no request. The loop list adds one batched query.

**Constraints**:
- ADR pins: 2 (arithmetic and policy in code), 5 (fail open), 6 (state = title + capped text + inflow), 7 (one Noul with its own bars), 8 (a Noul never licenses a fact; promotion changes loop state only).
- Dependency rule: plugins pass `source_ref` as a plain string to the opaque extractor callable.
- Pre-v1: the extractor signature changes at every caller in one change, with no shim.

**Scale/Scope**: Single user.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First | PASS: spec clarified with the user's answers; D2 governs |
| II. Single-User | PASS |
| III. Layered Packages | PASS: all logic in ze-worldstate; plugins get a keyword on an opaque callable; ze-api only wires and serializes; no new `ze_core` import |
| IV. Typed Python | PASS: dataclasses `SourceKey`, `LoopSource`, `CorroborationSurfaceConfig`, `CorroborationDecision`; `get_logger`; Pydantic only in `schemas.py` |
| V. Test Discipline | PASS: fakes by default; pg tests opt-in; calibration never collected |
| VI. Explicit Persistence | PASS: raw-SQL Alembic migration in the owning package |
| VII. One Gateway | PASS: System One through `SystemOneClient` on OpenRouter; E5 local for the baseline |
| VIII. Pre-v1 Hard Cuts | PASS: signature changes at all callers; no compatibility kwargs |

**Post-design re-check**: `decide()` is pure. Both bars live in one surface block, off by default. Fallback equals 170 behavior, asserted by running 170's extraction tests unchanged with the surface off. PASS.

## Blast radius (graphify `affected --depth 2`, plus grep for opaque callables)

| Symbol changed | Callers by package |
|---|---|
| `propose_loop_candidates` (new `source` kwarg) | ze-worldstate: `admission.py`, `inflow.py`; tests `test_extraction.py` (10 tests), `test_contribution.py`, `test_admission.py` |
| `_create_suspected_loop` / declared match (170) | ze-worldstate: `_commit_admitted`, `propose_loop_candidates`; same tests |
| `LoopInflow` (`admit` reads `thread_id`; `extract` gains `source_ref`) | ze-worldstate: `inflow.make_loop_inflow_from_parts`, `make_loop_extractor_from_parts`; ze-api: `build_container` (container.py L598, L803); 19 tests in `test_admission.py` |
| extractor callable (`source_ref` keyword) | ze-messenger: `inbound/processor.py` L157; ze-calendar: `jobs/calendar_reminder.py` L61; ze-ingestion: `sink.py` L67; ze-api: `app.py` lifespan, `seed.py`, `container.from_config` (construction only) |
| `LoopStore` Protocol (+5 methods) / `PostgresLoopStore` | ze-worldstate: `bootstrap.build_worldstate_stack`, `test_store.py`, `test_graph_integration.py`; ze-api: `container.py`, `compose.py`. One implementation; the fakes in ze-worldstate tests need the new methods |
| `LoopListItem` / `LoopDetail` | ze-api: `api/routes/loops.py`, `tests/api/test_loops_route.py`; ze-client generated types; ze-web: `entities/loop/api/useLoopsQuery.ts`, `widgets/loop-review/ui/LoopReviewList.tsx` and 171's page |
| `ze_worldstate.rest.list_loops` / `get_loop` | ze-api `routes/loops.py` |

Re-run `graphify update .` and the same `affected` queries after 170 and 171 land (task T001).

## Project Structure

### Documentation (this feature)

```text
specs/phases/172-corroboration-promotion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── corroboration-judgment.md   # flow, independence, question, decision table, config, invariants
│   └── sources-and-rest.md         # source keys through inflows, REST fields, web label
├── checklists/requirements.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
core/cognition/ze-worldstate/ze_worldstate/migrations/versions/zw003_open_loop_sources.py  # NEW
core/cognition/ze-worldstate/ze_worldstate/types.py               # SourceKey, LoopSourceRole, LoopSource; LoopAdmission.source
core/cognition/ze-worldstate/ze_worldstate/store.py               # add_source, list_sources, list_sources_for, promote, mark_source_promoted
core/cognition/ze-worldstate/ze_worldstate/corroboration_judge.py # NEW: question, state, surface config, decide()
core/cognition/ze-worldstate/ze_worldstate/corroboration.py       # NEW: constants, is_independent, corroborate_match
core/cognition/ze-worldstate/ze_worldstate/extraction.py          # source kwarg; origin rows; suspected branch + declared match call corroborate_match
core/cognition/ze-worldstate/ze_worldstate/admission.py           # admit() reads thread_id; extract(source_ref=); client passed to the commit
core/cognition/ze-worldstate/ze_worldstate/rest.py                # promoted, source_inflows, sources
core/cognition/ze-worldstate/README.md
core/cognition/ze-worldstate/tests/test_corroboration_judge.py    # NEW
core/cognition/ze-worldstate/tests/test_corroboration.py          # NEW
core/cognition/ze-worldstate/tests/test_extraction.py, test_admission.py, test_store.py  # extended
plugins/ze-messenger/ze_messenger/inbound/processor.py (+ test)
plugins/ze-calendar/ze_calendar/jobs/calendar_reminder.py (+ test)
core/ops/ze-ingestion/ze_ingestion/sink.py (+ test)
apps/ze-api/ze_api/api/schemas.py, api/routes/loops.py, tests/api/test_loops_route.py
apps/ze-api/tests/pg/test_loop_sources_pg.py                      # NEW (170 harness)
apps/ze-api/config/config.yaml                                    # system_one.surfaces.corroboration (off, null bars)
packages/ze-client/src/generated/*                                # make codegen
apps/ze-web/src/entities/loop/lib/format.ts (+ test), the 171 loop row component
eval/calibration/corroboration.jsonl, corroboration_holdout.jsonl, corroboration.py  # NEW
apps/ze-api/tests/calibration/test_corroboration_calibration.py   # NEW (offline shape)
Makefile                                                           # calibrate-corroboration (+ help, .PHONY)
docs/system-one.md, docs/configuration.md, docs/cognitive-architecture.md, docs/architecture.md,
docs/ingestion.md, docs/diagrams/root/open-loops.*, README.md, AGENTS.md, specs/README.md,
specs/arch/system-one-models.md, specs/arch/executive-function.md (§7 row 172)
```

**Structure Decision**: Loop-domain policy stays in ze-worldstate, typed against the `ze_agents` Protocol, as in 168. `corroboration.py` is separate from `extraction.py`, so the independence rule and the effects can be tested without the Haiku and matching scaffolding; `extraction.py` only calls it. The System One client reaches the commit through `LoopInflow`, which already holds it.

## Complexity Tracking

> No violations. Accepted: a fifth local copy of the tolerant bar reader (166 and 168 made the same call).
