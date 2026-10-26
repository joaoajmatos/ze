# Implementation Plan: AgentContext Derivation

**Branch**: `200-agent-context-derivation` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/200-agent-context-derivation/spec.md`, re-verified against main `5426cce1` (198 and 199 landed).

## Summary

One module in ze-agents, `ze_agents/derive.py`, owns every way to make a child `AgentContext`: `for_subtask`, `for_delegate`, `for_unattended` and `for_action`.
- A table in that module gives each field one rule per kind (inherit, given, or reset with a reason). The operations build contexts by walking the dataclass fields through the table, so a field cannot be dropped silently, and a test fails on a field with no rule.
- Write-gate, conductor and procedure-invocation state become three parts of the context (`WriteGateState`, `ConductorState`, `ProcedureInvocation`). Each is derived as one unit.
- A child run hands back one `ChildRunOutcome`, which ze-core merges into `AgentState` once per execution pass. `AgentState` becomes the only copy of conductor and procedure state between graph steps, which fixes the compound merge and two losses across a pause.
- `AgentState` and plugin state extensions declare each field's lifetime with `Annotated` markers (`Turn`, `Input`, `Thread`, `Run`). The new-turn graph input and the workflow step reset are generated from those markers, and graph build fails on an undeclared field.

## Technical Context

**Language/Version**: Python 3.12 (uv workspace)

**Primary Dependencies**: LangGraph 1.2.2 (verified to accept non-callable `Annotated` metadata on state fields, research R8), stdlib `dataclasses` and `typing`

**Storage**: none. No migration, no table change. Checkpointed shapes change (`AgentContext` fields, `AgentState.conductor_ledgers`, `procedure_invocations`); see Constitution VI.

**Testing**: pytest (`asyncio_mode=auto`) with `make test-agents`, `test-core`, `test-automation`, `test-personal`, `test-memory`, `test` (ze-api), and `make test-py` as the gate. No DB, no OpenRouter.

**Target Platform**: the Ze backend (local, self-hosted)

**Project Type**: monorepo engine refactor (ze-agents, ze-core, ze-automation, ze-personal, ze-memory, ze-api, ze-sdk)

**Performance Goals**: no change. Derivation is a dict walk over 31 fields per child run.

**Constraints**:
- REST, WS and stored `MessageTrace` JSON do not change.
- Plugins import the lifetime markers only through `ze_sdk.types`.
- ze-agents and ze-automation never import ze-core.

**Scale/Scope**:
- 7 construction sites become 4 operations.
- 15 flat context fields fold into 3 parts.
- About 40 test files touch the folded fields mechanically (list in `research.md` R3 and the blast radius below).

## Constitution Check

*Re-checked after Phase 1 design: PASS, no violations.*

- **I. Spec-First Development**: PASS. The spec is clarified, and this plan follows it. Three spec edits from re-verification are listed under "Spec amendments" below.
- **II. Single-User Model**: PASS. Not affected.
- **III. Layered Package Architecture**: PASS.
  - `derive.py` and `lifetime.py` live in ze-agents, which every caller already depends on.
  - ze-personal's `WorkflowAgentState` imports the markers from `ze_sdk.types`, not `ze_agents`.
  - The workflow reset wrapper is applied in ze-api (`wiring/workflow_graph.py`), the composition root that already joins ze-core and the plugin.
  - No new package edge.
- **IV. Typed, Explicit Python**: PASS. The new types are dataclasses in `types.py`, `derive.py` and `lifetime.py`. The two new errors (`UndeclaredDerivationError`, `UndeclaredLifetimeError`) subclass `ZeError`. FR-009 removes the `getattr` guards on context fields.
- **V. Test Discipline**: PASS. The table test, lifetime tests, a derivation test per kind, the merge tests, the workflow reset test and a timezone test per path (SC-005) all run offline.
- **VI. Explicit Persistence**: PASS, with an accepted pre-v1 consequence. No SQL changes. A checkpoint written before this phase may hold an `AgentContext` with the old flat fields. LangGraph's msgpack reviver returns `None` for a dataclass it cannot rebuild (`jsonplus._msgpack_ext_hook`, `except Exception: return`). So a turn that was paused across the upgrade answers "Missing routing envelope or agent context", and new turns are unaffected, because `agent_context` is reset every turn. There is no shim (Principle VIII).
- **VII. One LLM Gateway, Local Embeddings**: PASS. No model calls.
- **VIII. Pre-v1 Hard Cuts**: PASS.
  - The flat fields are removed in one change, not aliased.
  - `AgentState.conductor_ledger` is renamed to `conductor_ledgers` with every reader updated.
  - `AgentState.procedure_matches` is deleted.
  - `load_workflow_step`'s hand reset is deleted.
  - Old checkpoints are not migrated.

## Spec amendments made during planning

Engineering corrections, not product changes. They are recorded in the spec in the same commit as this plan.

1. FR-008: `compaction_span` was cut by phase 198. `AgentState.procedure_matches` is deleted because nothing reads it (committed with the re-verification, `91b5d5bb`).
2. Edge case "Two subtasks invoke a procedure" now states the decision (research R7): the trace shows the lowest subtask's invocation, and each invocation is completed with its own result.
3. Edge cases gain "Conductor run state": the soft deadline and stall details move off `extensions` into `ConductorState`, so a delegate's inherited `extensions` does not hand it the companion's deadline (research R3).

## Project Structure

### Documentation (this feature)

```text
specs/phases/200-agent-context-derivation/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R13 decisions
├── data-model.md        # parts, the 31-field derivation table, AgentState lifetimes
├── quickstart.md        # offline validation
├── contracts/derivation.md
├── checklists/requirements.md   # spec quality (specify)
├── checklists/derivation.md     # derivation and lifetime requirements (both kept)
└── tasks.md             # /speckit-tasks
```

### Source code (files this phase touches)

```text
core/contracts/ze-agents/ze_agents/
├── types.py            # WriteGateState, ConductorState, DelegateTally, ProcedureInvocation; AgentContext regrouped
├── derive.py           # NEW: DERIVATION table, for_subtask/for_delegate/for_unattended/for_action, RuntimeHandles, ChildRunOutcome, outcome_of
├── lifetime.py         # NEW: Turn/Input/Thread/Run markers, field_lifetimes, turn_reset
├── errors.py           # UndeclaredDerivationError, UndeclaredLifetimeError
├── base_agent.py       # reads ctx.write_gate / ctx.conductor / ctx.procedure_invocation; run_undo → for_action
├── budget.py           # soft deadline on ctx.conductor.deadline
└── delegate.py         # for_delegate; tally/ledger/stalls on ctx.conductor
core/contracts/ze-agents/tests/   # test_derive_table.py, test_derive.py, test_lifetime.py (new) + folded-field updates
packages/ze-sdk/ze_sdk/{types.py,errors.py}   # re-export markers and errors
core/cognition/ze-memory/ze_memory/procedures/tools.py   # invoke_procedure sets ctx.procedure_invocation
core/engine/ze-core/ze_core/
├── orchestration/state.py              # lifetimes on AgentState; conductor_ledgers, procedure_invocations; build_state_type validates; with_turn_reset
├── orchestration/child_runs.py         # NEW: runtime_handles, gate_input, conductor_input, tally_from, procedure_input, merge_outcomes, turn_ledger
├── orchestration/nodes/execution.py    # for_subtask on both paths; one merge per pass; kwargs helpers and copy-back deleted
├── orchestration/nodes/context.py      # stops copying conductor state onto the turn context; procedure_matches key dropped
├── orchestration/nodes/routing.py      # writes conductor_ledgers
├── orchestration/nodes/trace.py        # turn_ledger(state); procedure from state; fallback deleted
├── orchestration/nodes/memory.py       # complete_procedure_invocations(state, config)
├── orchestration/procedure_activation.py   # state-based usage trace and completion; per-subtask guided actions
├── conversation/turn.py                # make_graph_input generated from lifetimes
└── container.py                        # Container.state_type
core/automation/ze-automation/ze_automation/goals/executor.py
plugins/ze-personal/ze_personal/graph/workflow.py   # Run markers; reset list deleted
apps/ze-api/ze_api/{wiring/workflow_graph.py,wiring/container.py,api/ws/ui_actions.py}
docs/{architecture.md,sdk.md,workflows.md}, core/contracts/ze-agents/README.md, packages/ze-sdk/README.md, AGENTS.md, specs/README.md
```

**Structure Decision**: an engine refactor inside the existing packages. The two new modules sit in ze-agents (R1, R8), and one new helper module sits in ze-core (`child_runs.py`, R5 and R7).

### Blast radius (`graphify affected <symbol> --depth 1`, graph built on main 2026-10-26)

| Symbol | Source references by package | Test references | What changes for callers |
|---|---|---|---|
| `AgentContext` | ze-agents 41, ze-core 20, ze-automation 8, ze-personal 7, ze-calendar 6, ze-news 4, ze-prospecting 3, ze-messenger 3, ze-finance 3, ze-worldstate 3, ze-priority 3, ze-memory 2, ze-ingestion 2, ze-api 2, ze-sdk 1, eval/calibration 2 | ~210 (ze-core 95, ze-agents 70, ze-api 11, ze-personal 7, ze-calendar 7, ze-automation 5, ze-messenger 5, ze-memory 3, others 7) | Only readers of the 15 folded fields change: `base_agent.py`, `delegate.py`, `budget.py`, `execution.py`, `trace.py`, `context.py`, `procedures/tools.py`, `procedure_activation.py`, `goals/executor.py`, plus about 40 test files (grep list in the contract task). Code that only types `ctx` does not change. |
| `AgentState` | ze-core 48 | ze-core 7 | Readers of `conductor_ledger` (`routing.py`, `context.py`, `execution.py`, `trace.py`, `turn.py`) and `procedure_matches` (`context.py`) |
| `make_graph_input` | ze-core 5, ze-api 2, ze-automation 1 (via the injected `begin_workflow_turn`) | ze-core 17, ze-api 2 | New optional `state_type`; `begin_workflow_turn` gains keyword `state_type`, bound by ze-api with `functools.partial` |
| `build_state_type` | ze-core 2, ze-api 2 | ze-core 3 | Now validates lifetimes; `test_state_extensions.py` fixtures need markers |
| `run_delegate` | ze-agents 3 | ze-agents 12, ze-core 2 | Signature unchanged; builds through `for_delegate` |
| `_execute_single` / `_execute_compound` / `_conductor_kwargs` / `_sync_procedure_invocation` | ze-core 1–2 each | via `test_execution.py` | Rewritten or deleted |
| `ParkedSubtask` | ze-core 6, ze-api 2 | ze-core 2 | Unchanged type; `_run_with_timeout` returns `(result, outcome)` |
| `load_workflow_step` | ze-api 2 | ze-personal 7 | Returns only step keys; wrapped by `with_turn_reset` |
| `WorkflowAgentState` | ze-personal 3 | ze-api 6 | Fields get `Run` markers |
| `record_guided_actions` / `complete_procedure_invocation` / `procedure_usage_trace` | ze-core 2 each | ze-core 2–3 | State-based; per-subtask |
| `invoke_procedure` | (ze-memory tool) | ze-memory 1 | Sets `ctx.procedure_invocation` |

No plugin source changes apart from ze-personal's `workflow.py`. The plugin agents in ze-calendar, ze-news, ze-finance, ze-prospecting and ze-messenger only type `ctx`. Their tests that set `retry_mode=` or `pre_approved_writes=` on a context change mechanically (contract step).

## Seams for later phases

| Phase | Seam this phase leaves | Where |
|---|---|---|
| 201 typed turn services | `child_runs.runtime_handles(config, stream=…)` is the only derivation code that reads `config["configurable"]`, for `reporter`, `identity_builder`, `abort_token`, `embedder`, `token_sink`, `tool_sink` and `script_runner`. `gate_input` reads `pre_approved_writes` from config. `fetch_context` reads `retry_mode` and `user_message_id`. 201 replaces those bodies with typed services or the turn request; `derive.py` does not change. `Container.state_type` moves into the services. | `ze_core/orchestration/child_runs.py`, `ze_core/container.py`, `nodes/context.py` |
| 208 trace recorder | The conductor section reads `turn_ledger(state)`, `conductor_hint` and the tally from `AgentState`. The procedure section reads `state["procedure_invocations"]`. Both come from one `merge_outcomes` per pass; the context fallback is gone. | `child_runs.turn_ledger`, `procedure_activation.procedure_usage_trace(state)` |
| 209 write gate | All write-gate inputs are `ctx.write_gate: WriteGateState`. | `ze_agents/types.py` |
| 214 unattended step runner | Milestones build their context with `for_unattended`. 214 replaces that call with the turn pipeline. | `goals/executor.py` |

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first, T001–T014): the parts and the regrouped `AgentContext` (`types.py`), `lifetime.py`, `derive.py` complete with its table, the two errors and the `ze_sdk` re-exports, and the lifetime markers on `AgentState` and `WorkflowAgentState` (`state.py` gains `conductor_ledgers`, `procedure_invocations`, the deleted `procedure_matches`, `build_state_type` validation and `with_turn_reset`).

The contract also includes the **mechanical** move of every reader of the 15 folded fields and of `conductor_ledger`, behaviour unchanged, so the floor stays green. This covers `base_agent.py`, `budget.py`, `delegate.py` (field access only), `procedures/tools.py`, `procedure_activation.py`, `execution.py`, `context.py`, `routing.py`, `trace.py`, `turn.py` (the renamed key only), `goals/executor.py` (resume kwargs to `WriteGateState`), and about 40 test files.

After the contract merges, each file below has exactly one owner.

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `ze_agents/{types,derive,lifetime,errors,budget}.py`, `ze_agents/tests/test_{derive_table,derive,lifetime}.py`, `ze_core/orchestration/state.py`, `ze_core/tests/orchestration/test_state_{lifetimes,extensions,serde}.py`, `packages/ze-sdk/ze_sdk/{types,errors}.py`, `ze_memory/procedures/tools.py`, `ze_agents/tests/test_run_undo.py`, `ze_agents/base_agent.py` (after contract: only `lead`), the mechanical test edits of the contract; integration and final gates | T001–T014, T040–T043 | - | Vigil |
| engine | Sonnet ENG | `ze_core/orchestration/nodes/{execution,context,routing,trace,memory}.py`, `ze_core/orchestration/{child_runs,procedure_activation}.py`, `ze_core/tests/orchestration/nodes/test_execution*.py`, `ze_core/tests/orchestration/test_{conductor_merge,write_confirmation_compound,write_confirmation_e2e,procedure_activation,message_trace,retry_mode}.py` | T015–T026 | contract step | Vigil |
| edges | Sonnet ENG | `ze_agents/delegate.py`, `ze_agents/tests/test_delegate.py`, `ze_core/conversation/turn.py`, `ze_core/container.py`, `ze_core/tests/conversation/test_make_graph_input.py`, `ze_automation/goals/executor.py`, `ze_automation/tests/goal_engine/test_executor*.py`, `plugins/ze-personal/ze_personal/graph/workflow.py`, `plugins/ze-personal/tests/graph/`, `apps/ze-api/ze_api/{wiring/workflow_graph.py,wiring/container.py,api/ws/ui_actions.py}`, `apps/ze-api/tests/{test_workflow_hold.py,test_workflow_graph_timed.py,test_workflow_turn_reset.py,api/ws/test_ui_actions.py}` | T027–T039 | contract step | Vigil |
| docs | Haiku DOCS | `docs/{architecture,sdk,workflows}.md`, `core/contracts/ze-agents/README.md`, `packages/ze-sdk/README.md`, `AGENTS.md`, `specs/README.md` (200 row only) | T044–T046 | engine and edges merged | Vigil |

**Rules**:
- One lane per file.
- `lead` alone edits `types.py`, `derive.py`, `lifetime.py` and `state.py` after the contract. A lane that needs a rule or field change there asks `lead`, so a table change stays one edit (SC-004).
- `base_agent.py` changes only in the contract step: `run_undo` → `for_action` is done there too (T013), so `edges` does not touch it.
- `engine` and `edges` share no file. Engine owns the conductor merge; edges owns delegate inheritance, which only reads `ConductorState` through `derive.py`.
- Each lane works on a sub-branch of the floor branch. `lead` merges engine → edges → docs, then runs T040–T043.
- Each lane is reviewed as it finishes.
- No Haiku JR lane: every non-doc task needs design judgment on the derivation or the merge.

## Complexity Tracking

None.

## Analysis

`/speckit-analyze`, 2026-10-26, after tasks. There are no CRITICAL or HIGH findings and no constitution conflict. Coverage: 14 of 14 FR and 5 of 5 SC have tasks. Fixed in place:

| ID | Severity | Finding | Fix |
|----|----------|---------|-----|
| F1 | MEDIUM | FR-010 did not allow the pause fixes or per-subtask guided actions | FR-010 names them |
| F2 | MEDIUM | FR-011 implied `loop_active` is inherited | FR-011: it always starts `False` |
| F3 | MEDIUM | Spec named two lifetimes; plan has four | FR-006 and the Field lifetime entity name all four |
| F4 | MEDIUM | 198's B1/B6 regression tests not protected by a task | T017, T024, T028, T029 keep them |
| F5 | MEDIUM | "Per declaring class" reading was unneeded | Verified that a merged cross-module `TypedDict` resolves on Python 3.12.8; `turn_reset(state_type)` takes the merged type |
| F6 | LOW | Spec had three kinds; plan adds `action` | FR-001, the Derivation entity, SC-001 and the edge case updated |
| F7 | LOW | "Ledger delta" wording | Child run outcome entity reworded |
| F8 | LOW | T043 and T045 both edited `AGENTS.md`/`specs/README.md` | Rows belong to `docs` |
| F9 | LOW | T012 rg glob could miss nested test dirs | `**/tests/**/*.py` |
| F10 | LOW | R3 omitted `ProcedureInvocation.subtask` | Added |

## Review

Vigil, 2026-10-26, range `5426cce1..29582177`: **APPROVE**. Fixed in place:

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 1 | MEDIUM | `complete_procedure_invocations` indexed `subtask_results[i]`, but that list is ordered by completed index | Pair through `completed_subtask_indexes` (contract, R4, T022); T021 adds the skipped-subtask case |
| 2 | LOW | `conductor_ledgers` slots beyond routing's single slot were undefined | A missing slot reads `[]`; the merge pads (R5, R7, data-model); T018 (g) |
| 3 | LOW | Spec Context field counts were off | 19 named + up to 19 spread; delegate 20 |
| 4 | INFO | Two checklists | Both kept; the tree says so |
