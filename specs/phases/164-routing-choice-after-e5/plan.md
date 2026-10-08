# Implementation Plan: Routing Choice After E5

**Branch**: `164-routing-choice-after-e5` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/164-routing-choice-after-e5/spec.md` (clarified 2026-10-08). Governing: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O2.

## Summary

`EmbeddingRouter` keeps E5 encoding, the 160 bars and the ranked list. When `system_one.surfaces.routing` is enabled and calibrated, every multi-agent turn sends one batched System One request (`max_attempts=1`) over a bounded state `{user, history?, context?}` with three questions:
- a Choice over the top-k E5 agents plus `none`,
- a Noul: "needs more than one of these specialists?",
- a Score over three ordered complexity levels.

Pure code decides **trust / decompose / abstain / skip**:
- **Trust**: Choice names a shortlisted agent at or above `choice_trust` and the Noul is below `multi_specialist_hold`. `is_compound=False`, `confidence` = Choice peakedness, no Haiku.
- **Decompose**: Choice is `none` (any peakedness), or a trusted pick with Noul at or above `multi_specialist_hold`. `is_compound=True`; the existing `decompose` node and 153/155 rewrite run unchanged.
- **Abstain**: Choice below `choice_trust`. The 160 cosine bars decide, exactly as today.
- **Skip**: surface off, a null bar, or a client skip. The 160 path runs byte-for-byte.

The Score maps lookup to `simple` and the other two levels to `complex`. It replaces the regex on the embedding path and in the `decompose` node, when a Score is consumed.

Two hard cuts ride along:
- one router factory replaces the two diverging `EmbeddingRouter` construction sites (production drift fix);
- `judgments_from_result` takes question kinds instead of guessing from ids, so Score skip rows carry `kind="score"`.

A calibration set (EN+PT JSONL) and an opt-in live script produce the bars. The surface ships off with null bars.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Existing only. `SystemOneClient` (162, `ze_agents.system_one`), `OpenRouterSystemOneClient` (162), `build_system_one_client`. No new packages.

**Storage**: No migration. `messages.trace.judgments` already holds rows (162). `routing_log.confidence` keeps its column; its meaning follows `routing_method`/judgments (Clarifications).

**Testing**: pytest with a fake `SystemOneClient` (async `evaluate(state, questions, *, max_attempts=None)`) and the existing `make_embedder` pattern. Runs under `make test-core`, `make test` (ze-api), `make test-agents`. The calibration script is opt-in and never collected by pytest.

**Target Platform**: ze-api process, graph node `embed_route` then optional `decompose`.

**Project Type**: monorepo backend change inside `core/engine/ze-core` plus wiring in `apps/ze-api`, config, eval data and docs. No web change.

**Performance Goals**: One System One request per multi-agent turn, single attempt, bounded by `system_one.timeout_ms` (2000 ms default), no retry sleeps. Clear singles with a trusted Choice make zero generative calls (SC-001).

**Constraints**:
- Principle VII: System One stays on `/systemone`; Haiku decompose stays on `LLMClient`; E5 encoding unchanged.
- FR-005: `apply_conductor_rewrite`, `decompose`, 153/155 tests unchanged.
- FR-006: skip is byte-identical to 160.
- Pin 6 (minimal state): `user` text capped; history hint keeps its existing truncation; no `AgentState` dump.
- Dependency graph: all of this stays in `ze-core`. Plugins gain nothing; `ze_sdk` unchanged.

**Scale/Scope**: Single user; one request per multi-agent turn when enabled.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source: `.specify/memory/constitution.md`.*

| Principle | Assessment |
|---|---|
| I. Spec-First Development | PASS — 164 spec clarified; ADR O2 governs |
| II. Single-User Model | PASS — no tenant scoping |
| III. Layered Package Architecture | PASS — judge and factory live in ze-core; plugins untouched; ze-api only calls the factory |
| IV. Typed, Explicit Python | PASS — dataclasses (`RoutingSurfaceConfig`, `RoutingDecision`, `RoutingJudgment`); `get_logger`; fail-open returns, no bare exceptions |
| V. Test Discipline | PASS — fake client; no live vendor call in default suites (SC-005); calibration outside pytest |
| VI. Explicit Persistence | PASS — no schema change, no `routing_log` migration |
| VII. One LLM Gateway, Local Embeddings | PASS — judgments via OpenRouter System One; Haiku via `LLMClient`; E5 untouched |
| VIII. Pre-v1 Hard Cuts | PASS — one router factory replaces both call-site constructions; `judgments_from_result(question_ids=…)` replaced by `question_kinds=…` with the 163 caller updated; no shim |

**Post-design re-check**:
- `decide()` is pure and owns every bar (pin 2, pin 7).
- The Choice bar, Noul bar and Score bar are three separate keys (pin 7).
- Skip equals 160 (FR-006, SC-004).
- Default config is off with null bars, so existing fixtures see zero change.

PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/164-routing-choice-after-e5/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── routing-judgment.md     # questions, state, decision table, config
│   ├── router-factory.md       # one factory, both call sites, drift fix
│   └── envelope-judgments.md   # confidence semantics, envelope fields, trace rows, kind fix
├── checklists/requirements.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
core/engine/ze-core/ze_core/routing/judge.py                   # NEW: questions, state, RoutingSurfaceConfig, decide()
core/engine/ze-core/ze_core/routing/factory.py                 # NEW: build_embedding_router, router_config_from
core/engine/ze-core/ze_core/routing/router.py                  # route(..., judgment_state=), Choice flow, envelope build
core/engine/ze-core/ze_core/routing/types.py                   # RoutingEnvelope.judgment, .complexity_source; RoutingJudgment
core/engine/ze-core/ze_core/routing/__init__.py                # export factory
core/engine/ze-core/ze_core/bootstrap.py                       # build_router(stack, settings) → factory
core/engine/ze-core/ze_core/container.py                       # step 9 → factory; build system_one_client
core/engine/ze-core/ze_core/orchestration/nodes/routing.py    # embed_route: state, judgment rows; decompose: keep Score complexity
core/engine/ze-core/ze_core/conversation/messages/judgments.py # question_kinds; score skip kind
core/engine/ze-core/ze_core/orchestration/nodes/memory.py      # 163 caller: pass question_kinds
apps/ze-api/ze_api/container.py                                # build_router(shared, settings)
apps/ze-api/config/config.yaml                                 # system_one.surfaces.routing
core/engine/ze-core/tests/routing/test_routing_judge.py        # NEW: decide() table, questions, config
core/engine/ze-core/tests/routing/test_router_choice.py        # NEW: US1/US2/US3, skip identity
core/engine/ze-core/tests/routing/test_router_factory.py       # NEW: YAML, overrides, fallback, client, one factory
core/engine/ze-core/tests/routing/test_calibration_dataset.py  # NEW: routing.jsonl shape
core/engine/ze-core/tests/conversation/test_judgments.py       # score skip kind
core/engine/ze-core/tests/orchestration/nodes/test_routing_nodes.py  # judgments in state; decompose keeps Score
eval/calibration/routing.jsonl                                 # NEW: labeled EN+PT set
eval/calibration/routing.py                                    # NEW: opt-in live calibration
Makefile                                                       # calibrate-routing target
specs/arch/system-one-models.md                                # sequencing → 164 status
specs/core/ze-core.md                                          # routing judgment + factory
docs/configuration.md                                          # system_one.surfaces.routing keys
AGENTS.md                                                      # phase table row 164
```

**Structure Decision**: The judge is routing policy, so it lives in `ze_core/routing/` beside the router. It is typed against the `ze_agents` Protocol. The router is constructed in exactly one place (`factory.py`), which also fixes the production drift where `bootstrap.build_router` ignored YAML, `models.overrides`, `router_fallback` and now would have lacked the client. There is no web change (see research R9).

## Complexity Tracking

> No constitution violations.
