# Implementation Plan: Judgment Surface

**Branch**: `202-judgment-surface` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/202-judgment-surface/spec.md`

## Summary

One module, `ze_agents.judgment`, takes over what every System One judgment point repeats today: reading `system_one.surfaces.<name>`, the calibrated rule, the single-attempt call, exception → skip, warn-once and one `Judgment` record that carries the surface and the bar for each question. Each surface keeps its questions, its state builder, its config dataclass (now declaring `SURFACE`, `BARS` and `EXTRAS`) and its pure `decide()`. ze-core turns a record into trace rows with `judgment_rows(judgment)` and nothing else, so `judgment_bars.py`, `RoutingJudgment`, `SkillsJudgment`, the six `*_surface_config` parsers and the dead `fact_judge` row path are deleted. A failed commitment-intake call now writes skip rows like the other three conversation-turn surfaces. One calibration harness in `eval/calibration` holds row loading, set-shape checks, the live loop, the reliability and bar-grid reports, the verdict printout, saving and loading results and the config read; the six System One runners use it and build every config through the production parser. Golden output, captured from the current runners with a deterministic replay client before they change, proves calibration is unchanged.

Research: [research.md](research.md). Data: [data-model.md](data-model.md). Contracts: [contracts/judgment-surface.md](contracts/judgment-surface.md), [contracts/calibration-harness.md](contracts/calibration-harness.md). Verification: [quickstart.md](quickstart.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: ze-agents (new module), ze-core (routing, tier, nodes, trace rows, checkpoint serde), ze-skills, ze-worldstate, ze-memory (one dataclass), structlog via ze-logging, LangGraph `JsonPlusSerializer` (allowlist only)

**Storage**: none. No migration (no chain touched; the next free revisions on main stay unused: `zc042`, `zm027`, `zw007`).

**Testing**: pytest (`asyncio_mode=auto`), fake System One clients, structlog `capture_logs`; calibration golden files under `apps/ze-api/tests/calibration/golden/`. No real OpenRouter call, no database.

**Target Platform**: Ze running locally (self-hosted)

**Project Type**: monorepo (core packages, ze-api, eval scripts). No web change.

**Performance Goals**: none new. The trace gains at most seven rows on a failed commitment-intake call.

**Constraints**: pre-v1 hard cuts; ze-core never imported by ze-skills, ze-worldstate or ze-memory; `decide()` behaviour and shipped bars unchanged (FR-012); `JudgmentTrace` shape unchanged (no REST or WS change); 203 edits the same worldstate files (Coordination with 203).

**Scale/Scope**: about 25 source files, about 45 test files (mostly construction and import edits), 9 calibration files plus a harness, about 10 docs.

## Constitution Check

*GATE: passed before Phase 0 and re-checked after Phase 1.*

- **I. Spec-First Development**: PASS. Spec, clarifications (2026-10-26) and this plan exist. Status moves to Implemented in the commit that finishes the phase.
- **II. Single-User Model**: PASS. No user scoping.
- **III. Layered Package Architecture**: PASS. The module is in ze-agents (core/contracts), which every consumer already depends on. ze-core converts records to its own trace rows. No new import edge; plugins are untouched; `ze_sdk` is unchanged.
- **IV. Typed, Explicit Python**: PASS. Frozen dataclasses for every new type; no Pydantic outside `ze_api/api/`. The warn-once state uses `functools.lru_cache` (Complexity Tracking).
- **V. Test Discipline**: PASS. US1 starts with failing tests that force a client exception per surface; US2 with a test surface; US3 with golden output captured before the refactor. Fake clients only.
- **VI. Explicit Persistence**: PASS. No schema change. The checkpoint allowlist gains two modules, with a round-trip test.
- **VII. One LLM Gateway, Local Embeddings**: PASS. The System One client contract is unchanged.
- **VIII. Pre-v1 Hard Cuts**: PASS. Carriers, `judgment_bars.py`, the six parsers, `TierJudge.warn_uncalibrated_once`, the `fact_judge` branch and `FactAdmission`'s four fields are deleted. Inside the phase, the contract step adds the new API beside the old one and T044 deletes the old one before review; nothing old survives the phase.

**Doctrine functions served** (`docs/cognitive-architecture.md`): Governance (the trace is Ze's honesty surface, US1), and the System One judgments that Executive (routing, complexity, skills), Perception (commitment intake, loop gate) and Memory (fact admission) depend on. No function gains or loses a licence.

## Project Structure

### Documentation (this feature)

```text
specs/phases/202-judgment-surface/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── judgment-surface.md
│   └── calibration-harness.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
core/contracts/ze-agents/ze_agents/
├── judgment.py                 # NEW: SurfaceConfig, SurfaceBar, Judgment, DecisionUse, gate, judge, surface_block, parse_bar
└── system_one.py               # loses surface_block, parse_bar (T044)
core/engine/ze-core/ze_core/
├── checkpoint_serde.py         # + ze_agents.judgment, ze_agents.system_one
├── conversation/messages/judgments.py   # judgment_rows replaces judgments_from_result
├── orchestration/judgment_bars.py       # DELETED
├── orchestration/nodes/{routing,skills,tier,memory}.py
└── routing/{judge,router,types,tier,factory}.py
core/automation/ze-skills/ze_skills/{judge,matching,types,bootstrap}.py
core/cognition/ze-worldstate/ze_worldstate/{loop_judge,admission,corroboration_judge,corroboration,commitment_judge,intake,types}.py
core/cognition/ze-memory/ze_memory/types.py          # FactAdmission
apps/ze-api/ze_api/api/v0/system/models.py           # ComplexitySurfaceConfig.from_settings
eval/calibration/
├── harness.py                  # NEW
└── {routing,skills,complexity,loop_gate,corroboration,commitment_intake,commitment_intake_baseline,open_query}.py
apps/ze-api/tests/calibration/{replay.py,capture_golden.py,golden/,test_calibration_golden.py}   # NEW
```

**Structure Decision**: one new module in `core/contracts/ze-agents`, one in `eval/calibration`; everything else edits existing files in their owning packages.

## Blast radius

`graphify affected "<symbol>" --depth 2` on the floor checkout after `graphify update .` (2026-10-26), cross-checked with `rg` (graphify finds no edges for `LoopAdmission`, which `rg` does). Callers by package:

| Symbol | Production callers | Test callers |
|---|---|---|
| `judgments_from_result` | ze-core: `embed_route`, `match_skills`, `choose_tier`, `write_memory` | ze-core: `test_judgments`, `test_tier_node`, `test_memory`, `test_skills_node`, `test_routing_nodes`, `test_judgment_bars`, `test_memory_judgments`, `test_context_continuity_composition`, `test_extractor_dual_write`, `test_nodes`, `test_tool_sink`, `test_retry_rewind`, `test_turn_telemetry_stamp` (13 modules) |
| `bar_map`, `intake_bars` (`judgment_bars.py`) | ze-core: the same four nodes | ze-core: `test_tier_node`, `test_skills_node`, `test_routing_nodes`, `test_judgment_bars`, `test_memory`, `test_memory_judgments`, `test_compaction_readout` (ze-api `test_workflow_hold` is a graph edge only; it names none of these) |
| `surface_block` | ze-agents; ze-core: `routing/judge.py`, `routing/tier.py`, `judgment_bars.py`; ze-skills: `judge.py`; ze-worldstate: `loop_judge.py`, `corroboration_judge.py`, `commitment_judge.py` (7) | ze-agents `test_system_one`; surface judge tests in ze-core, ze-skills, ze-worldstate |
| `parse_bar` | the same surface modules; `judgment_bars.py` | ze-agents `test_system_one`; ze-core `test_tier` |
| `routing_surface_config`, `complexity_surface_config` | ze-core: `routing/factory.py`; ze-api: `api/v0/system/models.py` (complexity) | ze-core: `test_routing_judge`, `test_tier`, `test_router_factory`, `test_container_tier_judge`; ze-api: `test_container_tier_judge`; eval: `complexity.py` |
| `skills_surface_config` | ze-skills: `bootstrap.py` | ze-skills: `test_skills_judge`, `test_bootstrap` (ze-api `test_agent_wiring` is a graph edge only) |
| `loop_gate_surface_config`, `corroboration_surface_config`, `commitment_intake_surface_config` | ze-worldstate: `admission.py`, `corroboration.py`, `intake.py` | ze-worldstate: `test_loop_judge`, `test_corroboration_judge`, `test_commitment_judge`, `test_corroboration`, `test_corroboration_flow`, `test_intake` |
| `RoutingJudgment` | ze-core: `router.py` (`_judge`, `_envelope`, `_score_and_route`), `tier.py` (`choose`), `types.py` (`RoutingEnvelope`) | ze-core: `test_judgment_bars`, `test_routing_nodes` |
| `SkillsJudgment` | ze-skills: `matching.py` | ze-skills: `test_types` |
| `LoopAdmission` | ze-worldstate: `admission.py`, `intake.py`, `extraction.py` (reads `decision` only) | ze-worldstate: `test_admission`, `test_intake`; ze-api: `pg/test_loop_resolve_pg` (builds `LoopAdmission(decision=...)`, unaffected) |
| `IntakeAdmission` | ze-worldstate: `intake.py` (`admit`, `_fallback`, `_apply`); ze-core `write_memory` reads it by attribute | ze-worldstate: `test_intake`; ze-core: `test_judgment_bars`, `test_memory` |
| `FactAdmission` | ze-memory: `extractor.py` (`facts`, `path` only); ze-worldstate: `intake.py` | ze-memory: `test_extractor_admission`; ze-core: `test_judgment_bars` |
| `decide_tier` | ze-core: `tier.py` | ze-core: `test_tier`; eval: `complexity.py` |
| `TierJudge` | ze-core: `factory.py`, `container.py` (type only), `nodes/tier.py` | ze-core: `test_tier_node`, `test_tier`, `test_router_factory`, `test_tier_graph`, `test_judgment_bars`, `test_container_tier_judge`; ze-api: `test_container_tier_judge` |
| `LoopInflow`, `CommitmentIntake` | ze-api: `wiring/container.py`, `wiring/hooks.py` (constructors unchanged) | ze-worldstate: `test_intake`, `test_admission`, `test_loop_evidence_plumbing`, `test_corroboration_flow` |
| `RoutingEnvelope.judgment` | checkpointed in `AgentState` | ze-core: `test_checkpoint_serde`, `orchestration/test_state_serde` |

No plugin, `ze_sdk` or web code is reached.

## Coordination with 203

Agreed with Tarn (floor 203) on 2026-10-26 (the "202 Handoffs" note holds both messages); 203's plan records the same split.

- **Order**: 202 lands first. 203 builds on main in parallel and rebases onto 202 before review.
- **`admission.py`**: `LoopInflow.finish` is the junction. 202 changes its signature to `finish(text, provenance, decision, *, judgment=None)` and rewrites `_judge` and `_log`. 203 then removes the commit attachment in `finish`, deletes `commit_for`, adds one public commit method, deletes `LoopAdmission.commit` and makes `source` (and the commit's text and inflow) constructor fields.
- **`types.py`**: 202 replaces `LoopAdmission`'s judgment fields with `judgment: Judgment | None`. 203 never touches that field; 202 never touches `commit` or `source`.
- **`intake.py`**: 202 owns `IntakeAdmission`'s judgment fields, the judging block in `admit()` and `_fallback`'s record. 203 owns `_LOOP_KIND`, `_apply`'s loop branch and `_loop_admission`; 202's only edit in `_loop_admission` is dropping the `skip_reason=` argument the new `finish` no longer takes.
- **`commitment_judge.py`**: 202 moves the config dataclass onto `SurfaceConfig` and deletes the parser and `_BAR_NAMES`; it leaves `decide()` alone. 203 changes the `IntakeOutcome` loop kinds and the matching returns.
- **`loop_judge.py`**: 202 moves the config dataclass and deletes the parser. 203 owns `DecisionKind` and `LoopGateDecision` (FR-009).
- **`corroboration.py`**: 202 owns `_judge` and the config and warning block in `_corroborate`; 203 owns the effect side (about lines 164-199).
- **`nodes/memory.py`**: 202 owns the judgment-row hunk (`_outcome_row`, lines 83-101, and lines 156-193). 203 owns the loop-commit hunk (lines 197-201).
- **`eval/calibration`**: 202 owns it. After rebasing, 203 edits only the loop-kind string literals that read its vocabulary (`commitment_intake.py` and `loop_gate.py`).
- In 202 one lane (`ws`) owns every shared worldstate file.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first, T001–T007): `core/contracts/ze-agents/ze_agents/judgment.py` with the full interface of [contracts/judgment-surface.md](contracts/judgment-surface.md) and its tests; `judgment_rows` beside the old `judgments_from_result` in `ze_core/conversation/messages/judgments.py`; the two checkpoint-allowlist modules and a round-trip test. The old `surface_block`, `parse_bar` and `judgments_from_result` stay until T044, so every lane's branch builds and tests green on its own.

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `core/contracts/ze-agents/ze_agents/{judgment,system_one}.py`, `core/contracts/ze-agents/tests/{test_judgment,test_system_one}.py`, `core/engine/ze-core/ze_core/conversation/messages/judgments.py`, `core/engine/ze-core/tests/conversation/test_judgments.py`, `core/engine/ze-core/ze_core/checkpoint_serde.py`, `core/engine/ze-core/tests/test_checkpoint_serde.py`; merges; final gates | T001–T007, T044–T047 | - | Vigil |
| engine | Sonnet ENG | `core/engine/ze-core/ze_core/routing/{judge,router,types,tier,factory}.py`, `core/engine/ze-core/ze_core/orchestration/nodes/{routing,skills,tier}.py`, `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (judgment-row hunks only, lines 83-101 and 156-193), `core/engine/ze-core/ze_core/orchestration/judgment_bars.py` (delete), `apps/ze-api/ze_api/api/v0/system/models.py`, `core/engine/ze-core/tests/` (every file except `conversation/test_judgments.py`, `test_checkpoint_serde.py` and `routing/test_calibration_{dataset,script}.py`, `routing/test_companion_research_check.py`), `apps/ze-api/tests/test_container_tier_judge.py`, `core/automation/ze-skills/ze_skills/{judge,matching,types,bootstrap}.py`, `core/automation/ze-skills/tests/` | T008–T021 | contract step | Vigil |
| ws | Sonnet ENG | `core/cognition/ze-worldstate/ze_worldstate/{loop_judge,admission,corroboration_judge,corroboration,commitment_judge,intake,types}.py` (judgment side, see Coordination with 203), `core/cognition/ze-worldstate/tests/`, `core/cognition/ze-memory/ze_memory/types.py` (`FactAdmission` only), `core/cognition/ze-memory/tests/test_extractor_admission.py` | T022–T029 | contract step | Vigil |
| calib | Sonnet ENG | `eval/calibration/*.py`, `apps/ze-api/tests/calibration/`, `core/engine/ze-core/tests/routing/test_calibration_dataset.py`, `core/engine/ze-core/tests/routing/test_calibration_script.py`, `core/engine/ze-core/tests/routing/test_companion_research_check.py`, `core/arbitration/ze-priority/tests/test_open_query.py`, `Makefile` (the `calibrate-*` recipes only) | T030–T043 | T030–T031 after the contract step; T032 on after `engine` and `ws` are merged | Vigil |
| docs | Haiku DOCS | `docs/system-one.md`, `docs/configuration.md`, `docs/eval.md`, `docs/architecture.md`, `docs/testing.md`, `core/contracts/ze-agents/README.md`, `core/engine/ze-core/README.md`, `core/automation/ze-skills/README.md`, `core/cognition/ze-worldstate/README.md`, `core/cognition/ze-memory/README.md`, `AGENTS.md`, `specs/README.md` (202 row), `specs/phases/202-judgment-surface/spec.md` (Status line only) | T048–T051 | all lanes merged | Vigil |

**Rules**:

- **One lane per file.** `nodes/memory.py` is the one shared source file: `engine` edits only its judgment-row hunks; 203 owns the loop-commit hunk on its own floor.
- **Branches and merge order.** Each lane works on a sub-branch of the floor branch. `lead` merges `engine` → `ws` → `calib` → `docs`, then runs T044–T047. `engine` merges before `ws` because `engine` deletes the ze-core tests that build `FactAdmission` with judgment fields, which `ws` removes.
- **Each lane's own gate**: `engine` runs `make test-core test-skills`; `ws` runs `make test-worldstate test-memory`; `calib` runs `make test` (ze-api) and its golden test; `lead` runs `make test-py lint` after each merge.
- **`calib` captures golden output first** (T030–T031), on the contract-step commit, before `engine` or `ws` change any surface. It rebases onto the floor branch after `engine` and `ws` merge, then refactors the runners.
- **Cross-lane reads by attribute.** `write_memory` (engine) reads `intake.judgment` as a `Judgment`; `ws` builds it. Both build against [contracts/judgment-surface.md](contracts/judgment-surface.md); `lead`'s full `make test-py` after the `ws` merge is the integration check.
- **No Haiku JR lane.** Every code task needs design judgment inside the contract; only docs from a finished diff go to Haiku.
- **Graphify.** Run `graphify affected "<Symbol>" --depth 2` before changing a public symbol and update every caller it lists in the same change; the table above is the starting list.
- **Reviewer.** Vigil reviews each lane as it finishes (small diffs) and the whole floor before review state.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Process-level warn-once state in `ze_agents.judgment` (`functools.lru_cache` helpers), outside the two files AGENTS.md names for `lru_cache` singletons | SC-006 requires the uncalibrated warning at most once per surface per process, and the worldstate surfaces re-parse config per call with no long-lived object (corroboration is a free function) | A flag on each orchestrator is per instance, not per process, and corroboration has none; a plain module-level `set` is the mutable global the convention forbids; `reset_surface_warnings()` keeps tests isolated |
