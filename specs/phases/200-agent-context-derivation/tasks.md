---
description: "Tasks for phase 200: AgentContext Derivation"
---

# Tasks: AgentContext Derivation

**Input**: `specs/phases/200-agent-context-derivation/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/derivation.md`, `quickstart.md`)

**Tests**: required. The spec's independent tests and SC-002, SC-003 and SC-005 are tests. Write each test first and see it fail.

**Migration**: none. No table changes. Checkpointed shapes change: see plan, Constitution VI.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Lane]**: the owning lane from plan.md's Lane Plan: `[L:lead]`, `[L:engine]`, `[L:edges]`, `[L:docs]`. A task touches only files its lane owns.
- **[Story]**: US1, US2 or US3 (spec.md)

**Crew**: `lead` (Sonnet) lands the contract step T001–T014 on the floor branch first. `engine` (Sonnet) and `edges` (Sonnet) then work in parallel on sub-branches. `docs` (Haiku) starts when both have merged. The reviewer is Vigil, per lane as it finishes. Tick each box in the commit that finishes the task.

Repo-root paths below:
- `AG` = `core/contracts/ze-agents`
- `ZC` = `core/engine/ze-core`
- `ZA` = `core/automation/ze-automation`
- `ZP` = `plugins/ze-personal`
- `API` = `apps/ze-api`

---

## Phase 1: Setup

- [x] T001 [L:lead] Record the baseline on the floor branch: `make test-py` and `make lint`. Write any pre-existing failure into the "200 Handoffs" note, so no lane mistakes it for its own.

---

## Phase 2: Foundational — the contract step (blocks every story)

**Purpose**: the parts, the derivation owner, the lifetime markers and the mechanical move of every reader. Behaviour is unchanged and the floor stays green at the end of T014.

- [x] T002 [P] [L:lead] Write `AG/tests/test_lifetime.py` (failing first). Cover:
  - `field_lifetimes` on a `TypedDict` with `from __future__ import annotations` and forward refs returns each marker.
  - A field with no marker raises `UndeclaredLifetimeError`; the message names the class and the field.
  - `turn_reset` returns only `Turn` keys.
  - Two `turn_reset` calls never share a list or dict (mutate one, check the other).
  - `Input`, `Thread` and `Run` keys are omitted.
  - A merged `type("M", (A, B), {})` `TypedDict` built from two modules with forward refs resolves, and `turn_reset(M)` covers both bases.
- [x] T003 [L:lead] Implement `AG/ze_agents/lifetime.py` (`Turn`, `Input`, `Thread`, `Run`, `field_lifetimes`, `turn_reset`) per `contracts/derivation.md`. Add `UndeclaredLifetimeError` and `UndeclaredDerivationError` (both `ZeError`) to `AG/ze_agents/errors.py`. T002 passes.
- [x] T004 [L:lead] In `AG/ze_agents/types.py`, add `WriteGateState`, `DelegateTally`, `ConductorState` and `ProcedureInvocation`, and regroup `AgentContext` into the 31 fields of `data-model.md`. The 15 flat fields go: no alias, no property (Principle VIII). Keep the "runtime-only, never checkpoint" comments on the fields that stay.
- [x] T005 [P] [L:lead] Write `AG/tests/test_derive_table.py` (failing first):
  - `set(DERIVATION) == {f.name for f in fields(AgentContext)}`, so a missing row is named in the assertion message (SC-002).
  - Every `Reset` has a non-empty `reason` and every `Given` a `source`.
  - An operation called while a field lacks a row raises `UndeclaredDerivationError` naming it. Patch `DERIVATION` to drop one row.

  Write `AG/tests/test_derive.py`, one test class per kind:
  - `for_subtask` inherits `timezone`, the notes, skills and `procedure_guidance`/`procedure_matches`, and copies `extensions` (mutating the child's leaves the turn's alone); it takes `prompt`, `model`, `messages`, runtime, gate, conductor and procedure from its arguments.
  - `for_delegate` inherits `timezone`, `embed_fn`, `memory_store`, `reporter`, `identity_builder`, `abort_token`, `tool_sink` and `script_runner`; it merges `extensions` with `_delegate_depth = parent + 1`; and it resets `token_sink`, the five notes, `preset`, skills, procedure state and narrowing, and `conductor` (so `conductor.deadline is None`) (FR-012).
  - The delegate's `write_gate` keeps `retry_mode`, `decisions`, `pre_approved`, `round` and `approval_request_id`, with `resume` = the argument and `loop_active=False` (FR-011).
  - `for_unattended` gives the timezone, `memory_store`, `extensions`, `pre_approved` and the held resume, with `retry_mode=False`, and no notes or handles.
  - `for_action` sets only `session_id`.
  - `outcome_of` stamps `procedure.subtask = index` and keeps the same `tally` object.
- [x] T006 [L:lead] Implement `AG/ze_agents/derive.py` per `contracts/derivation.md` and the `data-model.md` table. Write every `Reset` reason and `Given` source as a sentence, from data-model.md and research R6, R11 and R12. The operations walk `dataclasses.fields(AgentContext)`; no field list is written by hand. T005 passes.
- [x] T007 [P] [L:lead] Re-export from `packages/ze-sdk/ze_sdk/types.py`: `Turn`, `Input`, `Thread`, `Run`, `WriteGateState`, `ConductorState`, `DelegateTally`, `ProcedureInvocation`. Re-export `UndeclaredLifetimeError` from `packages/ze-sdk/ze_sdk/errors.py`. Update `__all__`. `make test-sdk` passes, including `test_plugin_boundaries.py`.
- [x] T008 [L:lead] In `ZC/ze_core/orchestration/state.py`:
  - Put `Annotated[..., <marker>]` on every `AgentState` key, per the `data-model.md` lifetime table.
  - Rename `conductor_ledger` to `conductor_ledgers: list` (one ledger per subtask).
  - Add `procedure_invocations: list` and delete `procedure_matches`.
  - `build_state_type` calls `field_lifetimes` on `AgentState` and on each extension before merging.
  - Add `with_turn_reset(node, state_type)`: an async wrapper returning `{**turn_reset(state_type), **await node(state, config)}`.

  Tests:
  - New `ZC/tests/orchestration/test_state_lifetimes.py`: every key is declared (SC-003); the reset values equal the data-model table; an extension `TypedDict` with an unmarked field makes `build_state_type([plugin])` and `build_graph(..., plugins=[plugin])` raise `UndeclaredLifetimeError` naming the field (US3 scenario 3); `with_turn_reset` output starts from the reset and lets the node's keys win.
  - Update the fixtures in `ZC/tests/orchestration/test_state_extensions.py`.
  - Add a round trip of the four new dataclasses inside `AgentContext` to `ZC/tests/orchestration/test_state_serde.py`.
- [x] T009 [L:lead] In `ZP/ze_personal/graph/workflow.py`, give the ten `WorkflowAgentState` fields `Run("...")` markers imported from `ze_sdk.types`. Change only annotations here; `edges` deletes the reset list in T036. `make test-personal` passes.
- [x] T010 [L:lead] Mechanical move in ze-agents and ze-memory, behaviour unchanged:
  - `AG/ze_agents/base_agent.py`: `ctx.write_gate.*` for the seven gate fields, `ctx.conductor.hint` for the routing hint, `ctx.procedure_invocation.tool_names` for the narrowing, the `procedure_invocation is None` check at the old `:1008`, and `getattr(ctx, …)` guards on `AgentContext` fields replaced by plain attribute reads (FR-009).
  - `AG/ze_agents/budget.py`: the soft deadline lives on `ctx.conductor.deadline`; `_SOFT_DEADLINE_KEY` is deleted.
  - `AG/ze_agents/delegate.py`: field access only. Use the tally, ledger and `stalls` on `ctx.conductor`, and `ctx.write_gate.*` in the still hand-built `sub_ctx`. `for_delegate` comes in T028.
  - `core/cognition/ze-memory/ze_memory/procedures/tools.py`: `invoke_procedure` sets `ctx.procedure_invocation = ProcedureInvocation(...)`.
- [x] T011 [L:lead] Mechanical move in ze-core and ze-automation, behaviour unchanged:
  - `ZC/ze_core/orchestration/nodes/execution.py`: the helpers build the parts; the copy-back targets the parts.
  - `nodes/context.py`: the conductor part is filled from state with `conductor_ledgers[0]`; the `procedure_matches` return key is dropped.
  - `nodes/routing.py`: returns `conductor_ledgers: [ledger]`.
  - `nodes/trace.py`: the ledger is flattened from `conductor_ledgers`.
  - `ZC/ze_core/conversation/turn.py`: renamed key only.
  - `ZC/ze_core/orchestration/procedure_activation.py`: reads `ctx.procedure_invocation`.
  - `ZA/ze_automation/goals/executor.py`: `_HeldResume.context_kwargs()` becomes `gate()`, returning a `WriteGateState`; `_execute_milestone` passes `write_gate=`.
- [x] T012 [L:lead] Mechanical test updates. Find every test that sets or reads a folded field or `conductor_ledger`:

  ```
  rg -l 'ctx\.(resume|write_decisions|pre_approved_writes|write_round|approval_request_id|loop_active|retry_mode|conductor_|procedure_invo|procedure_tool_names)|(write_decisions|pre_approved_writes|write_round|approval_request_id|loop_active|conductor_[a-z_]+|procedure_invo[a-z_]+|procedure_tool_names)=|"conductor_ledger"|"procedure_matches"' --glob '**/tests/**/*.py' core plugins apps packages
  ```

  The list includes `AgentContext(retry_mode=…)` kwargs. Rewrite each to the parts; assertions keep their meaning. The list in `research.md` R3 counts about 40 files across ze-agents, ze-core, ze-memory, ze-automation, ze-calendar, ze-messenger and ze-api.
- [x] T013 [L:lead] `AG/ze_agents/base_agent.py` `run_undo` builds its context with `for_action(session_id)`, keeping `retry_mode=False` explicit through the action defaults. `AG/tests/test_run_undo.py` passes unchanged in meaning.
- [x] T014 [L:lead] Contract gate:
  - Run `make test-agents test-core test-memory test-automation test-personal test-sdk test`, then `make test-py` and `make lint`. All are green against the T001 baseline.
  - Commit the contract.
  - Post in "200 Handoffs" that `engine` and `edges` may start, with the contract commit hash.
  - Request review: `python3 scripts/process/review.py request <base>..<head> Vigil`.

**Checkpoint**: the contract is merged; `engine` and `edges` start in parallel.

---

## Phase 3: User Story 1 — every agent run sees the turn it belongs to (P1) 🎯 MVP

**Goal**: routed agents, compound subtasks, delegates and goal milestones get the turn's timezone and `extensions`; each derivation is the only place that decides what a child gets.

**Independent Test**: `test_derive_table.py` (T005), plus one Lisbon-time test per path (SC-005).

### Engine lane (routed agent and compound subtask)

- [x] T015 [P] [L:engine] [US1] Write `ZC/tests/orchestration/nodes/test_execution_derivation.py` (failing first). The turn context has `timezone="Europe/Lisbon"` and `extensions={"user_message_id": "m1"}`. Check:
  - The single-path child context and each compound subtask context carry both values.
  - A stub agent's `_build_system_prompt` line shows Lisbon time (SC-005, US1 scenario 1).
  - A stub agent reading `ctx.extensions["user_message_id"]` (as the workflow agent does, `ze_automation/agents/workflow/agent.py:108`) gets `"m1"` when routed (US1 scenario 2).
  - Only the single path gets a `token_sink`.
  - An image turn's child gets the image message.
- [x] T016 [L:engine] [US1] Create `ZC/ze_core/orchestration/child_runs.py` with `runtime_handles(config, *, stream)`, `gate_input(turn, state, config, index)` (moves `_pre_approved` and `_resume_kwargs`), `tally_from(state)`, `conductor_input(state, index, tally)` and `procedure_input(state, index)`.
- [x] T017 [L:engine] [US1] In `ZC/ze_core/orchestration/nodes/execution.py`, both paths build the child with `for_subtask(...)` from `child_runs`. Delete `_conductor_kwargs`, `_prompt_note_kwargs`, `_procedure_kwargs`, `_pre_approved`, `_resume_kwargs` and the second hand-written list in `_make_ctx` (this also removes the misindented line). T015 passes. `ZC/tests/orchestration/nodes/test_execution_context_notes.py` and `test_execution.py` pass; update only the assertions that checked the deleted helpers. Keep phase 198's B1 timezone regression tests as they are.

### Edges lane (delegate, goal milestone, screen action)

- [ ] T027 [P] [L:edges] [US1] Extend `AG/tests/test_delegate.py` (failing first):
  - The specialist context of a delegate from a caller with Lisbon time and `user_message_id` has both, plus `_delegate_depth=1` (US1 scenarios 1, 4 and 5).
  - It has `embed_fn` and `memory_store`.
  - It has no `token_sink`, notes, skills, procedure state, or `conductor.deadline`, even when the caller's deadline is set (no `WRAP_UP_NOTE` in the specialist's loop).
  - `retry_mode` reaches it (edge case "Retry runs").
  - A depth-1 caller is still refused.
- [ ] T028 [L:edges] [US1] In `AG/ze_agents/delegate.py`, build `sub_ctx` with `for_delegate(ctx, prompt=prompt, resume=resume)`. Delete the hand-written construction. T027 and the rest of `test_delegate.py` pass, including phase 198's B1 delegate timezone test.
- [ ] T029 [P] [L:edges] [US1] In `ZA/ze_automation/goals/executor.py`, `_execute_milestone` builds with `for_unattended(session_id=…, prompt=…, timezone=self._timezone, memory_store=self._memory, extensions={"goal_id": …}, pre_approved=…, resume=resume.gate() if resume else None)`. Add a test in `ZA/tests/goal_engine/test_executor.py` that the milestone prompt shows the executor's timezone (SC-005). `test_executor_hold.py` passes (held resume), and so does phase 198's B1 milestone timezone test.
- [ ] T030 [P] [L:edges] [US1] `API/ze_api/api/ws/ui_actions.py` `_context` returns `for_action(thread_id)`. `API/tests/api/ws/test_ui_actions.py` passes.

**Checkpoint**: US1 is done when T015–T017 and T027–T030 are green.

---

## Phase 4: User Story 2 — conductor and procedure state come back in one value (P2)

**Goal**: one `ChildRunOutcome` per child, one merge per pass, `AgentState` as the only copy, and caps per turn across subtasks.

**Independent Test**: `ZC/tests/orchestration/test_conductor_merge.py`.

- [ ] T018 [P] [L:engine] [US2] Write `ZC/tests/orchestration/test_conductor_merge.py` (failing first), with stub companion and specialist agents and the write-confirmation harness (`write_confirmation_harness.py`):
  - (a) A single turn with two delegates gives state `conductor_delegate_total == 2`, two `done` entries in `conductor_ledgers[0]`, and the trace's `conductor_ledger` equal to them (US2 scenario 1).
  - (b) A delegate that parks, followed by approval and resume, gives total 1 and exactly one ledger entry, `awaiting_confirmation` then `done` (US2 scenario 3; today's total resets to 0).
  - (c) In a compound turn, two companion subtasks delegating once each give ledgers concatenated in subtask order and summed counts.
  - (d) In a compound turn, the subtasks together reach `DELEGATE_TURN_CAP`, and the next delegate in either subtask is refused with `ask_user` (US2 scenario 4).
  - (e) The per-specialist cap counts across subtasks.
  - (f) The same totals hold when one subtask pauses and resumes.
  - (g) A compound turn of three subtasks, with routing's one-slot `conductor_ledgers` (or none), where only subtask 2 delegates: subtasks 0 and 1 read `[]`, and the merged list is padded, `[[], [], [<entry>]]`.
- [ ] T019 [L:engine] [US2] Add `merge_outcomes(state, outcomes, tally)` and `turn_ledger(state)` to `ZC/ze_core/orchestration/child_runs.py`. `_run_with_timeout` in `nodes/execution.py` returns `(result_or_parked, outcome_of(ctx, index))`, and does so on `LoopParked` too.
- [ ] T020 [L:engine] [US2] In `nodes/execution.py`, `execute_tool` builds one `tally_from(state)` per pass, shares it across all subtasks, and returns `merge_outcomes(...)` on the single and the compound path. Stop mutating `base_ctx` and drop `"agent_context"` from the updates. Delete `_sync_procedure_invocation` and every copy-back (FR-005). `_out_of_time` reads `ctx.conductor.ledger`. T018 passes.
- [ ] T021 [P] [L:engine] [US2] Extend `ZC/tests/orchestration/test_procedure_activation.py` (failing first):
  - A single subtask's invocation is the turn's `procedure_invocations[0]`, and the trace's `procedure` matches it (US2 scenario 2).
  - In a compound turn with two invoking subtasks, each records its own guided actions and is completed with its own subtask's result; the trace shows the lowest index (research R7).
  - A procedure invoked before a pause is completed after the resume.
  - In a compound turn `[A, B (agent disabled), C]` where C invokes a procedure (`subtask=2`, `completed_subtask_indexes=[0, 2]`), C's invocation is completed with C's result: no `IndexError`, and not A's result.
- [ ] T022 [L:engine] [US2] `ZC/ze_core/orchestration/procedure_activation.py`:
  - `procedure_usage_trace(state)` reads `procedure_invocations[0]`.
  - `complete_procedure_invocations(state, config)` pairs each invocation with its subtask's result through `results_by_index = dict(zip(state["completed_subtask_indexes"], state["subtask_results"]))`, never `subtask_results[i]`: that list is ordered by completed index, and disabled or parked subtasks have no entry. On the single path it uses `agent_result`. An invocation with no result for its subtask is completed as abandoned.
  - `record_guided_actions(invocation, result, config)` is called from `execute_tool` per finished subtask.
  - Log `procedure_invocations_extra` when there is more than one.
- [ ] T023 [L:engine] [US2] Call sites:
  - `nodes/memory.py`: call `complete_procedure_invocations(state, config)`, keeping the `is_retry` skip.
  - `nodes/trace.py`: use `turn_ledger(state)`, the conductor hint from state, and the procedure from state; delete `_conductor_ledger`'s context fallback (FR-009).
  - `nodes/context.py`: stop setting conductor state on the turn context.
  - T021 passes.
- [ ] T024 [L:engine] [US2] Update the assertions that pinned the old hand copies in `ZC/tests/orchestration/test_write_confirmation_compound.py`, `test_write_confirmation_e2e.py`, `test_message_trace.py`, `test_retry_mode.py` and `nodes/test_execution.py`. Only assertions about copies change; behaviour assertions stay (FR-010), and so does phase 198's B6 test (`test_compaction_readout.py`).
- [ ] T025 [L:engine] [US2] Run the grep gate:
  - `rg -n 'getattr\((ctx|base_ctx|agent_context), "' ZC/ze_core/orchestration/nodes/{execution,trace}.py` finds no `AgentContext` field (FR-009).
  - `rg -n "_sync_procedure_invocation|base_ctx\.conductor|conductor_delegate_total = " core` finds nothing (FR-005).
- [ ] T026 [L:engine] [US2] Engine lane gate: `make test-core test-agents` green. Request review from Vigil on the lane range.

**Checkpoint**: US2 is done when T018–T026 are green.

---

## Phase 5: User Story 3 — the per-turn reset is complete by construction (P2)

**Goal**: the new-turn input and every workflow step reset are generated from the lifetime declarations.

**Independent Test**: `ZC/tests/conversation/test_make_graph_input.py` plus `ZC/tests/orchestration/test_state_lifetimes.py` (T008).

- [ ] T031 [P] [L:edges] [US3] Extend `ZC/tests/conversation/test_make_graph_input.py` (failing first):
  - Every `Turn` key of `AgentState` equals its reset value; every `Input` key comes from the `RawInput`; no `Thread` or `Run` key is present.
  - A `state_type` with an extra `Turn` key gets that key reset.
  - A two-turn graph run (with `write_confirmation_harness.build_graph`) shows that `loop_offer_ids`, `open_items_query`, `resume_recap_applied` and `pre_approved_writes` set in turn 1 start empty in turn 2 (US3 scenario 1, FR-008), and `messages` and `last_active_at` survive (US3 scenario 2).
- [ ] T032 [L:edges] [US3] `ZC/ze_core/conversation/turn.py`: `make_graph_input(raw, session_id, state_type=AgentState)` returns `{**turn_reset(state_type), **inputs}`. Delete the hand-kept dict and its docstring note about `messages`; keep the docstring's explanation of why `Thread` keys are absent. `make_graph_input_from_raw_text` is unchanged.
- [ ] T033 [L:edges] [US3] `Container.state_type` (default `AgentState`) in `ZC/ze_core/container.py`, set where the graph is built (`:369`) from `build_state_type(resolved_plugins)`. Set it in `API/ze_api/wiring/container.py` (`:626`). `invoke_raw_turn` and `Container.invoke` pass it to `make_graph_input`. T031 passes.
- [ ] T034 [P] [L:edges] [US3] Write `API/tests/test_workflow_turn_reset.py` (failing first). Build the workflow graph with stub nodes and run two steps: step 1 writes `judgments`, `components`, `tier` and a conductor ledger; step 2 starts with all four empty, while `workflow_steps`, `workflow_step_results` and `visit_counts` keep their values (US3 scenario 4). The cancel short-circuit still reaches `workflow_cancelled` with the step results.
- [ ] T035 [L:edges] [US3] `API/ze_api/wiring/workflow_graph.py`:
  - Register the node as `add_timed_node(builder, "load_workflow_step", with_turn_reset(load_workflow_step, state_type))`.
  - `begin_workflow_turn(workflow, *, state_type)` passes it to `make_graph_input`.
  - In `API/ze_api/wiring/container.py` (`:766`), inject `functools.partial(begin_workflow_turn, state_type=…)`. `ze_automation/bootstrap.py` does not change (research R10).
- [ ] T036 [L:edges] [US3] `ZP/ze_personal/graph/workflow.py`: `load_workflow_step` returns only its step keys (`steps_by_id`, `current_step_id`, `visit_counts`, `step_started_at`, `step_attempt`, `from_retry`, `prompt`, `pre_approved_writes`); delete the 14 hand-reset keys and update the docstring (FR-014). Update the assertions in `ZP/tests/graph/test_workflow.py` that pinned the reset keys. T034 passes.
- [ ] T037 [L:edges] [US3] Update `API/tests/test_workflow_hold.py` and `API/tests/test_workflow_graph_timed.py` for `begin_workflow_turn`'s new argument and the wrapped node.
- [ ] T038 [L:edges] [US3] Run the US1 and US3 regression: `make test-agents test-core test-automation test-personal test` green.
- [ ] T039 [L:edges] Edges lane gate: request review from Vigil on the lane range.

**Checkpoint**: all three stories are done.

---

## Phase 6: Polish and cross-cutting

- [ ] T040 [L:lead] Merge `engine`, then `edges`, into the floor branch and resolve. Run `make test-py` and `make lint`, both green.
- [ ] T041 [L:lead] Acceptance sweep, run from `quickstart.md`:
  - SC-001: `rg -n "AgentContext\(" --glob '*.py' core plugins apps packages integrations | rg -v /tests/` lists only `nodes/context.py` and `ze_agents/derive.py`.
  - SC-005: confirm the four timezone tests (T015 single and compound, T027 delegate, T029 milestone) are named in the run.
  - Record the results in "200 Handoffs".
- [ ] T042 [L:lead] Run `graphify update .`, then `graphify affected AgentContext --depth 1`, and confirm no new construction site. Save the outcome with `graphify save-result ... --memory-dir /Users/joaoamatos/coding/ze/graphify-out/memory`.
- [ ] T043 [L:lead] After the docs lane: tick every task, set `spec.md` Status to Implemented, and run the after_implement hook (`speckit-process-after-implement`). The `AGENTS.md` and `specs/README.md` rows belong to `docs` (T045).
- [ ] T044 [P] [L:docs] Public docs, following the `doc-style` skill:
  - `docs/architecture.md`: replace "Graph input factory" with how lifetimes generate the turn input and the workflow step reset; add an "Agent context derivation" subsection (one owner, four kinds, a delegate's inheritance, one outcome per child run).
  - `docs/sdk.md`: the `AgentContext` table gets `write_gate`, `conductor` and `procedure_invocation`; the `state_extensions()` row says every field needs a `Turn`/`Input`/`Thread`/`Run` marker from `ze_sdk.types` or startup fails; list the new `ze_sdk.types` exports and `UndeclaredLifetimeError`.
  - `docs/workflows.md`: line 86, where each step resets turn state through the engine's generated reset.
- [ ] T045 [P] [L:docs] Package READMEs and indexes:
  - `core/contracts/ze-agents/README.md`: module rows for `derive.py` and `lifetime.py`.
  - `packages/ze-sdk/README.md`: the `types.py` row names the lifetime markers.
  - `AGENTS.md`: layout rows for `derive.py`, `lifetime.py` and `ze_core/orchestration/child_runs.py`, and the phase 200 row, set to Implemented.
  - `specs/README.md`: the 200 row, set to Implemented.
- [ ] T046 [L:docs] Docs coverage check:
  - `git diff main...HEAD --stat` and `git diff main...HEAD -- '*.py' | rg '^\+(def|class) '`. Every renamed or new public symbol (`for_*`, `Turn`/`Input`/`Thread`/`Run`, `WriteGateState`, `ConductorState`, `ProcedureInvocation`, `conductor_ledgers`, `make_graph_input(state_type)`, `begin_workflow_turn(state_type)`) is described in a touched doc, or the docs lane notes why no public doc mentions it.
  - `rg -n "conductor_ledger\b|procedure_invocation_id|pre_approved_writes|write_decisions|AgentState.procedure_matches" docs README.md core/*/*/README.md packages/*/README.md` finds no stale mention.

---

## Dependencies and execution order

- **T001 → T002–T014** (contract, `lead`). T002, T005 and T007 can be written in parallel. T004 comes before T006 and T008. T010–T012 come after T004, T006 and T008.
- **After T014**: `engine` (T015–T026) and `edges` (T027–T039) run in parallel; they share no file.
  - Within engine: T015 → T016 → T017 → T018 → T019 → T020 → T021 → T022 → T023 → T024 → T025 → T026.
  - Within edges: T027 → T028; T029 and T030 any time; T031 → T032 → T033; T034 → T035 → T036 → T037 → T038 → T039.
- **T040–T042** (`lead`) after both lanes merge. **T044–T046** (`docs`) after T040. **T043** last.

## Parallel examples

- Contract: T002 (`test_lifetime.py`), T005 (`test_derive*.py`) and T007 (ze-sdk re-exports) at once.
- After the contract: the engine agent starts T015 while the edges agent starts T027, T029 and T030 together (three files), then T031 and T034.
- Docs: T044 and T045 at once, then T046.

## Implementation strategy

- **MVP**: the contract plus US1 (T001–T017, T027–T030). Every run gets the turn's timezone and `user_message_id` from one owner, and SC-001, SC-002 and SC-005 hold.
- **Then** US2 (the merge and caps per turn) and US3 (the generated reset), which are independent of each other after the contract.
- Each lane is reviewed as it finishes; `lead` integrates and runs the gates.
