# Implementation Plan: Complexity Routing

**Branch**: `182-complexity-routing` | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/182-complexity-routing/spec.md`. Scope signed off by the user on 2026-10-16 (spec Clarifications); every decision below is confirmed.

## Summary

Routing keeps choosing the agent and now always assigns the agent's **full** model. A new graph node, `choose_tier`, runs after `match_skills` and before `preflight` (the node phase 181 put in place of `capability_check`). For a single-agent turn whose agent declares a distinct `model_simple`, it builds a capped task state (task, conversation, recap, memory, focus, skill; the agent field was dropped in tuning, spec FR-006 amended 2026-10-16), asks System One one Noul (`needs_deep_reasoning`, one attempt), and swaps in `model_simple` only when the answer is at or below `simple_max`. Every other outcome keeps the full model. The surface `system_one.surfaces.complexity` ships off with a null bar in the implementation commits. It was enabled at `simple_max` 0.40 in a separate commit after the held-out ENABLE for English and Portuguese (2026-10-16).

Hard cuts in the same change: the regex `ComplexityEstimator`, the routing Score question and `complexity_lookup_max`, `RoutingEnvelope.complexity` / `complexity_source`, `EmbeddingRouter._resolve_model(agent, complexity)`, the `gold_complexity` field of the routing calibration sets, and the `routing_log.complexity` / `model_selected` columns.

The trace gains `MessageTrace.tier` (REST, `trace_update`, Routing section in ze-web). A new calibration (`make calibrate-complexity`, tuned + blind held-out multi-turn sets) decides whether a later, separate commit enables the surface.

## Technical Context

**Language/Version**: Python 3.12 (engine), TypeScript (ze-web tier line).

**Primary Dependencies**: Existing only: `SystemOneClient` / `SystemOneQuestion` / `SystemOneResult` (`ze_agents.system_one`), `resolve_model` (`ze_agents.model_resolution`), `judgments_from_result` (`ze_core.conversation.messages.judgments`), `criterion_for` (`ze_core.routing.judge`). No new package, no new package edge.

**Storage**: One migration on the ze-core `zc` chain dropping two `routing_log` columns. The chain head on this branch is `zc032`; floors 181 and 173 may land a `zc033` first, so T001 re-reads the chain and takes the next free number (`zc0NN_drop_routing_log_tier.py`, `down_revision` = current head).

**Testing**: pytest with `AsyncMock`/fakes and a call-counting fake `SystemOneClient` (pattern: `core/engine/ze-core/tests/support/routing.py`, `tests/routing/test_router_choice.py`). Node tests follow `tests/orchestration/nodes/test_routing_nodes.py`. Calibration scorer tests in `apps/ze-api/tests/calibration/` (pattern: `test_loop_gate_calibration.py`). Web: Vitest beside `RoutingBadge`. No live vendor call in default suites; the live calibration is never collected.

**Target Platform**: The conversation graph (`invoke_raw_turn`). Proactive goal/workflow executors are untouched.

**Performance Goals**: Off: zero added requests and latency. On: one System One request on tierable turns only (~0.45–0.6 s observed, 2 s timeout); the calibration runner reports p50/p90.

**Constraints**: ADR pins 2 (code owns the mapping), 5 (fail to the full model), 6 (named capped fields), 7 (one narrow Noul with its own bar), 10 (bars from Ze data, EN+PT). `ze_core` must not name plugin agents. Pre-v1 hard cuts, no fallback, no shim.

**Scale/Scope**: Single user; three tiered agents.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First | PASS: spec clarified and scope signed off 2026-10-16 |
| II. Single-User | PASS |
| III. Layered Packages | PASS: all engine logic in `ze_core` (`routing/tier.py`, `orchestration/nodes/tier.py`); `ze_api` wires and serializes; plugins untouched (they only declare `model_simple`) |
| IV. Typed Python | PASS: dataclasses `ComplexitySurfaceConfig`, `TierDecision`, `TierTrace`; Pydantic only in `schemas.py`; `get_logger` |
| V. Test Discipline | PASS: fail-first unit tests with fakes; calibration runner outside pytest; offline `--check-sets` test |
| VI. Explicit Persistence | PASS: raw-SQL Alembic migration in the owning package (ze-core `zc`) |
| VII. One Gateway | PASS: System One through `SystemOneClient` on OpenRouter |
| VIII. Pre-v1 Hard Cuts | PASS: regex, Score, envelope fields, router method and log columns deleted at every caller in one change |

**Post-design re-check**: `decide_tier()` is pure; off and uncalibrated are decided before any request; every non-consumed path yields `full`. PASS.

## Blast radius

`graphify update .` then `graphify affected` / `explain` (2026-10-16), completed with grep where the graph has no unique node (`ComplexityEstimator` is ambiguous to `affected`; field reads on `RoutingEnvelope` and `model_simple` class attributes are not edges).

| Symbol changed | Callers / readers by package |
|---|---|
| `ComplexityEstimator` (deleted) | ze-core: `routing/router.py` (ctor, `route_forced`, `_single_agent_envelope`, `_envelope`), `routing/factory.py` (`estimator` kwarg), `bootstrap.py` (`EngineStack.estimator`, `build_engine_stack` L112), `orchestration/nodes/routing.py` (`decompose` → `router._estimator.classify`); tests `tests/routing/test_complexity.py` (whole file) |
| `EmbeddingRouter._resolve_model` (replaced by `resolve_agent_model(agent, tier, config)`) | ze-core: `router.py` (`route_forced` L103, `_single_agent_envelope` L151, `_envelope` L222), `nodes/routing.py` `decompose` L116, `nodes/context.py` `_open_query_envelope` L175; tests `test_router.py` L213-235 (`test_uses_model_simple_for_simple_prompt`), `test_router_factory.py` L67-68, `test_routing_nodes.py` L505-537, `test_context.py` L450 |
| `RoutingEnvelope.complexity` / `complexity_source` (deleted) | ze-core: `router.py`, `nodes/routing.py` (`decompose`, `apply_conductor_rewrite` copies it), `nodes/context.py` `_open_query_envelope`, `routing/store.py` `write_log`; tests `test_router_choice.py` L193-320, `test_routing_nodes.py` L515-567, `test_context.py` L432 |
| `RoutingSurfaceConfig.complexity_lookup_max`, `RoutingDecision.complexity`, `Q_COMPLEXITY`, `_complexity`, `normalise_complexity_score`, `COMPLEXITY_SCORE_MAX` (deleted) | ze-core: `routing/judge.py` (`build_questions`, `decide`, `routing_surface_config`); eval: `eval/calibration/routing.py` (`grid_metrics` L408, `report` L547, lookup-bar suggestion, Score histogram); tests `test_routing_judge.py` L72-77, 96-110, 336-364, `test_router_choice.py` L26, 94, 125, `test_calibration_script.py` L43-132, `test_calibration_dataset.py` L25-82, `tests/support/routing.py` L102, `tests/conversation/test_judgments.py` L98-139, `test_routing_nodes.py` L413-473 |
| `build_embedding_router` (drops `estimator`; sibling `build_tier_judge` added) | ze-core: `bootstrap.build_router` L160, `container._build_router` L457 / `from_config` L357; ze-api: `container.build_container` L747; tests `test_router_factory.py` |
| `Container._build_config` / `ZeContainer._build_config` (add `tier_judge`) | ze-core `container.py` L45; ze-api `container.py` L289 |
| `graph_builder` edges (`match_skills → choose_tier → preflight`) | ze-core `orchestration/graph.py`, `orchestration/nodes/__init__.py`; no test asserts node names today (grep), so the node test is new |
| `MessageTrace` (+ `tier`) | ze-core `conversation/messages/types.py`, `nodes/trace.py` `record_trace` L71, `conversation/turn.py` (partial frame); ze-api `api/schemas.py` `MessageTraceResponse` L211 (wrapped by `MessageTraceEntry.trace`), `WsTraceUpdateFrame` L860 → `make codegen` (`@myguyze/ze-client`); ze-web `widgets/message-trace/ui/RoutingBadge.tsx`, `MessageTracePanel.tsx`, `widgets/trace-panel/ui/RoutingSection.tsx` |
| `routing_log` columns (dropped) | ze-core `routing/store.py` `write_log`; `001_initial_schema.py` (history only); `rest.py` and `RoutingLogEntry` do not select them |
| `model_simple` (semantics unchanged; now read by the tier step) | declared on companion, research (ze-personal), goals (ze-automation); `BaseAgent` attribute (ze-agents); `ze_api/testing.py` L44 and `tests/support/gate.py` L38 expose it (unchanged) |

No plugin, `ze_sdk` or `ze_agents` signature changes. `delegate_to_agent` unchanged (FR-013).

## Design

### `ze_core/routing/tier.py` (new)

- `Q_DEEP = "needs_deep_reasoning"`; instruction text (research R2); caps (research R3).
- `ComplexitySurfaceConfig(enabled: bool = False, simple_max: float | None = None)` with `calibrated`; `complexity_surface_config(settings)` parsing `system_one.surfaces.complexity` like `routing_surface_config` (reuse `_bar` from `judge.py`, renamed public `parse_bar`).
- `resolve_agent_model(agent_name, tier, app_config) -> str`: `tier == "simple"` and the class declares `model_simple` → `resolve_model(agent, model_simple, cfg)`, else `resolve_model(agent, model, cfg)`; unknown agent → `resolve_model(agent, None, cfg)`.
- `build_tier_question() -> dict[str, SystemOneQuestion]` (one Noul).
- `TierDecision(tier: Literal["simple","full"], decided_by: str, consumed: bool)`; pure `decide_tier(result, cfg) -> TierDecision` (table in [contracts/tier-judgment.md](contracts/tier-judgment.md)).
- `TierJudge(system_one_client, surface, app_config)` with `async choose(envelope, tier_state) -> TierOutcome(decision, model, judgment)`; never raises (client exceptions → skip). Built by `build_tier_judge(config, system_one_client)` in `routing/factory.py`.

### `ze_core/orchestration/judgment_state.py`

Add `build_tier_state(state) -> dict[str, str]` per research R3, reading `agent_context`, `memory_context`, `routing_hints`, `image_caption`/`prompt` (not the envelope: the agent field was dropped, spec FR-006 amended 2026-10-16). `build_judgment_state` and `history_hint` stay unchanged for routing and skills.

### `ze_core/orchestration/nodes/tier.py` (new): `choose_tier`

1. No envelope → `{}`.
2. Not tierable (FR-012) → `TierTrace(full, compound | no_simple_model)`, no request.
3. Judge absent, or surface off / uncalibrated → `TierTrace(full, off | uncalibrated)` (warn once per process on uncalibrated).
4. Otherwise set the cost agent context to `router`, call `judge.choose`, restore it; on `simple` replace `envelope.subtasks[0].model`.
5. Return `{"envelope", "tier", "judgments": [*existing, *rows]}`.

`AgentState` gains `tier`. `record_trace` copies it to `MessageTrace.tier`. `turn.py` emits a partial `trace_update` `{"tier": …}` on `on_chain_end` of `choose_tier`.

### Router and decompose (hard cut)

- `EmbeddingRouter` drops `estimator`; every path builds `SubTask(model=self._full_model(agent))`; `_envelope` drops the complexity branch.
- `judge.py`: `build_questions` returns `agent` + `multi_specialist` only; `decide` loses complexity; `RoutingSurfaceConfig` loses `complexity_lookup_max`.
- `decompose` node: `subtask.model = resolve_agent_model(subtask.agent, "full", router app config)`. `apply_conductor_rewrite` stops copying complexity; companion gets its full model.
- `_open_query_envelope`: full model.
- `bootstrap.EngineStack.estimator` removed.

### Wiring

- `config.yaml`: delete `complexity_lookup_max`; add `complexity: {enabled: false, simple_max: null}` with a dated comment.
- Both `_build_config` methods add `"tier_judge"`; both containers build it with `build_tier_judge(config, system_one_client)`.
- Graph: `match_skills → choose_tier → preflight`.

### Trace and storage

- `TierTrace(agent, tier, decided_by, model)` in `conversation/messages/types.py`; JSON-safe in `trace_update` (117 rule).
- ze-api: `TierTraceResponse`; `tier` on `MessageTraceResponse` (which `MessageTraceEntry` wraps as `trace`, so the entry carries no own `tier`) and on `WsTraceUpdateFrame`; `make codegen`.
- Migration `zc0NN_drop_routing_log_tier.py`: `ALTER TABLE routing_log DROP COLUMN IF EXISTS complexity, DROP COLUMN IF EXISTS model_selected`; downgrade re-adds both as nullable `TEXT`. `write_log` stops writing them.
- ze-web: `RoutingBadge` gets an optional `tier` prop and renders one line; `MessageTracePanel` and `RoutingSection` pass `trace.tier`.

### Calibration

- `eval/calibration/complexity.py` (pattern: `loop_gate.py` / `corroboration.py`): `--check-sets`, `--set tuned|holdout`, `--simple-max`, `--live` guard; state through `build_tier_state` on synthetic state; per-language report and verdict (FR-016).
- `eval/calibration/routing.py`: delete complexity code; routing `*.jsonl`: delete `gold_complexity`.
- `Makefile`: `calibrate-complexity`.

## Project Structure

### Documentation (this feature)

```text
specs/phases/182-complexity-routing/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── tier-judgment.md
│   └── holdout-brief.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
core/engine/ze-core/ze_core/
├── routing/tier.py                      # new
├── routing/{router,judge,factory,types,store}.py
├── routing/complexity.py                # deleted
├── orchestration/nodes/tier.py          # new: choose_tier
├── orchestration/{graph,state,judgment_state}.py
├── orchestration/nodes/{routing,context,trace,__init__}.py
├── conversation/{turn.py,messages/types.py}
├── bootstrap.py, container.py
└── migrations/versions/zc0NN_drop_routing_log_tier.py
apps/ze-api/ze_api/{container.py,api/schemas.py}  + WS schema, make codegen
apps/ze-api/config/config.yaml
apps/ze-web/src/widgets/{message-trace,trace-panel}/ui/
eval/calibration/{complexity.py,complexity.jsonl,complexity_holdout.jsonl,routing.py,routing*.jsonl}
Makefile
```

**Structure Decision**: engine-only change in `ze-core`, thin wiring in `ze-api`, one web line. Same split as 164.

## Docs touched ([DOCS] tasks)

`README.md` (L63 regex sentence), `docs/architecture.md` (cost-aware routing L78-93; graph flow; agent table "default model tier" L337), `docs/configuration.md` (routing surface L419-465; new `complexity` surface; `model_simple` L136), `docs/system-one.md` (surface table; routing L71-119), `docs/adding-an-agent.md` (L194, L230), `docs/sdk.md` (L184), `docs/package-architecture.md` (L161), `docs/eval.md` (calibration commands), `core/engine/ze-core/README.md` (L11, L26), `AGENTS.md` (layout `routing/` line, graph flow, commands, phase row 182), `specs/arch/system-one-models.md` (O2 note, new O11 row, Appendix A `ComplexityEstimator` row, Sequencing), `specs/README.md` index, status notes on 164 and 167 specs.

## Complexity Tracking

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| New graph node `choose_tier` | The judgment needs context that exists only after `fetch_context` / `match_skills` (user-pinned) | Inside routing (option E): no memory, recap, focus or skill |
| Migration dropping two columns | The route-time tier is no longer known; the columns would be wrong | Keep and write NULL: dead columns against Principle VIII |
