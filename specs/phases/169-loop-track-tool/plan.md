# Implementation Plan: Loop Track Tool

**Branch**: `169-loop-track-tool` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/169-loop-track-tool/spec.md` (clarified 2026-10-12, four user answers recorded). Governing: [`memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md), [`contribution-seam.md`](../../arch/contribution-seam.md).

## Summary

1. **Tool**: `track_loop(title, window_days=0)` on the loops agent (`ze_worldstate/agents/tools.py`). It delegates to a new injected service, `LoopTracker` (`ze_worldstate/tracking.py`), which owns normalize, clamp, entity resolution, matching and the four outcomes (`created`, `confirmed`, `reinforced`, `revived`).
2. **Write path**: create goes through `loop_to_contribution` + `submit_and_detect_collisions` (the same call shape as `_create_declared_loop`). Reinforce/confirm/revive are store edits on an existing claim.
3. **Store**: `transition(..., user_asked=False)` gains the `drifting → active` edge for `user_asked=True` only; new `stamp_declared()` writes `confirmed_at`, `updated_at`, deadline, confidence in one statement (FR-009).
4. **Gate skip**: `write_memory` skips `loop_admission` when a flattened `track_loop` call returned `ok: true`. The predicate `track_loop_succeeded()` lives in `ze_agents/nested_tools.py` beside `loop_review_earned`, so `ze_core` stays unaware of `ze_worldstate`.
5. **Honesty**: `enforce_domain_cancel_confirmations(..., strip_track_claims=False)` gains an opt-in tracking-claim family; only `LoopsAgent` turns it on (the goals agent shares the function and must not have "keep an eye on your goal" stripped).
6. **Evals**: `eval/scenarios/loops.yaml` (EN + PT track-then-list, with `verify` on `open_loops`), two routing training rows.

## Technical Context

**Language/Version**: Python 3.11+. No TypeScript.

**Primary Dependencies**: Existing only. `ze-worldstate` already depends on `ze-agents`, `ze-memory`, `ze-collision`, `ze-plugin`. No new package edge.

**Storage**: No migration. `open_loops` columns used: `state`, `confidence`, `confirmed_at`, `drift_deadline`, `drift_rationale`, `updated_at`.

**Testing**: pytest, `AsyncMock` pool/store fakes, a scripted fake `LLMClient` for the agent loop. `make test-worldstate`, `make test-agents`, `make test-core`, `make test` (ze-api), `make test-eval`, `make lint`. Live: `make eval` (opt-in).

**Constraints**:
- Dependency graph: `ze_core` never imports `ze_worldstate`; plugins untouched.
- Pre-v1 hard cut: `LoopsAgent.__init__` signature changes; every constructor call site is updated in the same change (no optional-tracker shim).
- Tool schema: parameters must be primitive-typed to appear in the LLM schema (`ToolSpec.llm_schema`), hence `window_days: int = 0`.
- Doctrine functions served: **Executive function** (active concerns, the user's stated priorities) and **Perception** (user-stated input becomes a claim); honesty is a **Reflection** concern (the reply must match the record).

## Blast radius (graphify affected, depth 2, run on this floor 2026-10-12)

| Symbol | Direct dependents | Action |
|---|---|---|
| `LoopStore` / `PostgresLoopStore` (`transition`, new `stamp_declared`) | `agents/agent.py`, `agents/tools.py`, `bootstrap.py`, `decay.py`, `extraction.py`, `matching.py`, `rest.py`, `jobs/drift_sweep.py`, `jobs/stale_suspicion.py`, `ze_priority/view.py`, `ze_api/api/routes/loops.py`, `ze_api/container.py`; tests `test_store.py`, `test_graph_integration.py` | Add a keyword-only param with default (no caller changes) and one new method. Update the Protocol and the Postgres impl. Any in-repo fake store implementing `LoopStore` must add `stamp_declared`. |
| `LoopsAgent` | `tests/test_loop_agent_cancel.py`, `apps/ze-api/tests/agents/test_bootstrap.py` (indirect), `bootstrap_agents` constructor injection | Constructor gains `loop_tracker: LoopTracker`; register `LoopTracker` in `dep_map` in `ze_api/container.py`. |
| `enforce_domain_cancel_confirmations` | `LoopsAgent.run/stream`, goals agent `run/stream` (`ze_automation/agents/goals/agent.py`) | New keyword-only flag, default off; goals agent unchanged. |
| `find_matching_loop` | `extraction.py` (`_close_matching_loop`, `_create_suspected_loop`), `admission.py`, `eval/calibration/loop_gate.py`, tests | Called, not modified. |
| `loop_to_contribution`, `propose_loop_candidates`, `LoopInflow` | `extraction.py`, `admission.py`, `inflow.py`, `ze_api/container.py` | Not modified. The gate is skipped in `write_memory`, not changed. |
| `write_memory` (`ze_core/orchestration/nodes/memory.py`) | graph, `test_loop_admission_node.py`, `test_memory*.py` | One predicate before the gather; existing cases unchanged. |
| `ze_agents/nested_tools.py` | the two agents above, tests | Add `track_loop_succeeded`, `track_loop_earned`, `_TRACK_CLAIM`. |

Boundary check for reviewers: `graphify path "ze_worldstate.tracking" "ze_core"` must return no path; `packages/ze-sdk/tests/test_plugin_boundaries.py` stays green.

## Design

See [research.md](research.md) for decisions and rejected alternatives, [data-model.md](data-model.md) for types and the lifecycle edge, [contracts/track-loop.md](contracts/track-loop.md) for the tool, outcomes and claim patterns, [quickstart.md](quickstart.md) for commands.

### Outcome algorithm (normative)

```
track(title, window_days):
  title = normalize(title)            # strip, collapse whitespace, cap 120 on a word boundary
  if not title: return error("empty title")
  window = clamp(window_days)         # 7 default; 1..365
  entity_ids = resolve_entities(title)   # fail open
  match = find_matching_loop(entity_ids, title, states=[suspected, active, drifting])   # skipped if no graph store
  now = utcnow(); deadline = now + window days
  match None        -> create (seam) -> stamp_declared -> link entities     => created
  match suspected   -> transition(ACTIVE) -> stamp_declared(0.9, deadline)  => confirmed
  match active      -> set_confidence(max(current, 0.9)); link entities     => reinforced
  match drifting    -> transition(ACTIVE, user_asked=True) -> stamp_declared => revived
```

## Phases

1. **Store and types** (BE): `transition(user_asked)`, `stamp_declared`, `TrackResult`.
2. **Tracker and tool** (BE): `LoopTracker`, `track_loop`, agent wiring, container DI.
3. **Honesty and gate skip** (BE): nested_tools predicates and enforcer, `write_memory` skip.
4. **Evals and calibration rows** (PLATFORM).
5. **Docs and indexes** (DOCS), then a coverage check against `git diff main...HEAD`.
