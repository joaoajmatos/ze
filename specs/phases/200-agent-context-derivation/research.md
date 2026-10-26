# Research: AgentContext Derivation

**Phase**: 200 | **Date**: 2026-10-26 | **Code read at**: `5426cce1` (main, after 198 and 199)

Each decision lists what was chosen, why, and what was rejected. No `NEEDS CLARIFICATION` remains; the four product questions were settled in the spec's Clarifications session.

## R1. Where the derivation lives

**Decision**: one new module, `core/contracts/ze-agents/ze_agents/derive.py`. It holds the declaration table and the four operations `for_subtask`, `for_delegate`, `for_unattended` and `for_action`, plus `RuntimeHandles` and `ChildRunOutcome`.

**Rationale**: the three callers sit in three packages. `delegate.py` is in ze-agents itself, `_execute_milestone` is in ze-automation, `execution.py` is in ze-core, and ze-api builds the screen-action context. ze-agents is the lowest package that all of them already depend on (`AGENTS.md` dependency graph), so the module adds no package edge. ze-core cannot own it: ze-agents and ze-automation may not import ze-core.

**Alternatives rejected**:
- *Classmethods on `AgentContext`*: `types.py` would hold behaviour and a 45-row rule table, and the dataclass would no longer be plain data.
- *ze-core `orchestration/derive.py`*: the delegate (ze-agents) and goal milestones (ze-automation) could not call it, so two derivations would remain.

## R2. How a field declares its inheritance

**Decision**: a table in `derive.py`, `DERIVATION: dict[str, FieldRule]`, one row per `AgentContext` field. A `FieldRule` gives one rule per kind (`subtask`, `delegate`, `unattended`, `action`). A rule is one of:
- `Inherit()`: copied from the parent (for `extensions`, a merge; see R6).
- `Given(source)`: an argument of the operation supplies it (prompt, messages, model, runtime handles, write-gate inputs, conductor input). `source` says where the value comes from.
- `Reset(reason)`: the field's dataclass default, with a sentence saying why.

Each operation builds its kwargs by walking `dataclasses.fields(AgentContext)` through the table. A field without a row raises `UndeclaredDerivationError` (new, in `ze_agents/errors.py`) when the operation runs. The table test (`tests/test_derive_table.py`) fails first and names the field. The write-gate, conductor and procedure parts are single fields of `AgentContext` (R3), so each is one row and is derived as one unit (FR-011).

**Rationale**: SC-004 asks for one place to edit. The table keeps every reason readable side by side and leaves `types.py` as plain data. Iterating `fields()` means a field cannot be silently dropped: the old bug class (a site forgets a field) can no longer happen.

**Alternatives rejected**:
- *`field(metadata={...})` on each `AgentContext` field*: it is the same single edit, but the reasons would sit across 45 field definitions and make `types.py` hard to read. The spec asks for a declaration "where derivation is defined", and the table is that place.
- *Four explicit constructor calls with a parity test*: two places to edit again (the call and the test).

## R3. Grouping the write-gate, conductor and procedure state

**Decision**: three dataclasses in `ze_agents/types.py` (already on the checkpoint allowlist, `ze_core/checkpoint_serde.py`) replace 18 flat fields:

- `WriteGateState`: `resume`, `decisions`, `pre_approved`, `round`, `approval_request_id`, `loop_active`, `retry_mode`. It is `AgentContext.write_gate` (FR-011). Phase 209's gate reads it. The name avoids a clash with 209's `WriteGate`.
- `ConductorState`: `hint`, `ledger`, `tally: DelegateTally` (`counts`, `total`), `deadline: float | None`, `stalls: dict[str, str]`. It is `AgentContext.conductor`.
- `ProcedureInvocation`: `invocation_id`, `procedure_id`, `version_id`, `tool_names`. It is `AgentContext.procedure_invocation: ProcedureInvocation | None`.

`procedure_guidance` and `procedure_matches` stay flat: they are turn inputs from `fetch_context`, not run results.

**Rationale**:
- FR-011 asks for the write-gate part.
- The compound cap (FR-013) needs one `DelegateTally` object that all subtasks of a pass share. An `int` field cannot be shared, which is exactly today's per-subtask total bug.
- One `ProcedureInvocation` value replaces four fields that `_sync_procedure_invocation` copies one by one (FR-005).
- The soft deadline (`budget._SOFT_DEADLINE_KEY`) and the stall details (`delegate._stall_key`) live in `extensions` today. They are the conductor's run state, not turn facts. Once `extensions` is inherited by delegates (FR-012), leaving them there would hand the companion's deadline to the specialist. Its loop would then append `WRAP_UP_NOTE` (`base_agent.py:903`), a behaviour change the spec does not allow. Moving them into `ConductorState` keeps `extensions` for turn facts (`user_message_id`, `goal_id`, `_delegate_depth`).

**Alternatives rejected**:
- *Keep the flat fields and share the dict only*: this is today's bug. The counts are shared but the total is not.
- *Group the runtime handles too*: out of scope (spec Assumptions). Phase 201 decides how handles travel.

## R4. Where conductor and procedure state live between passes

**Decision**: `AgentState` is the only copy between graph steps.
- `conductor_ledger: list` becomes `conductor_ledgers: list[list[dict]]`, one ledger per subtask index.
- `conductor_delegate_counts` and `conductor_delegate_total` stay as they are.
- The new `procedure_invocations: list[ProcedureInvocation]` is ordered by subtask, and each entry carries `subtask: int`.
- `fetch_context` stops copying conductor state onto the turn context. `execute_tool` builds each child's `ConductorState` from the state (R5) and writes the merged outcome back (R7).
- `record_trace` reads `turn_ledger(state)`, the flattened ledgers in subtask order, and `procedure_invocations[0]`. The trace fallback that prefers the context's copy (`trace.py:336-341`) is deleted.
- `write_memory` completes each invocation with its own subtask's result.

**Rationale**: the turn context in `state["agent_context"]` is checkpointed and was mutated in place, partly shared by reference (`counts`) and partly copied (`total`, an empty `ledger`). That is how a pause loses state. Two bugs found while re-checking:
- After a parked delegate resumes, `conductor_delegate_total` drops back to the pre-turn value, because the copy-back reads `base_ctx.total`, which the park path never updated.
- A procedure invoked before a pause is never completed, because the park path returns before `_sync_procedure_invocation`.

Keeping the state as the only copy fixes both and gives US2 scenario 3 ("preserved exactly once") a mechanism. Per-subtask ledgers are needed because `_update_conductor_ledger` matches entries by agent name. If two subtasks shared one ledger, one subtask's `done` could close the other's `running` entry.

**Alternatives rejected**:
- *One shared ledger with a hidden `subtask` key per entry*: the key would leak into the stored trace JSON, or a strip step would be needed.
- *Carry the ledger on `ParkedSubtask`*: ledgers of subtasks that finished in an earlier pass could then not be told apart from a parked subtask's snapshot.

## R5. Inputs to `for_subtask`

**Decision**:

```python
for_subtask(turn, *, prompt, model, messages, runtime, gate, conductor, procedure) -> AgentContext
```

- ze-core's new `orchestration/child_runs.py` builds the inputs from `state`, `config` and the subtask index:
  - `runtime_handles(config, stream=...)` returns a `RuntimeHandles`. The `stream` flag is set only on the single path, so compound subtasks get no `token_sink` (today's behaviour).
  - `gate_input(turn, state, config, index)` returns a `WriteGateState`: the `_pre_approved` union, `_resume_kwargs`, and `retry_mode` from the turn.
  - `conductor_input(state, index, tally)` returns a `ConductorState`: the state hint, a copy of `conductor_ledgers[index]`, and the shared tally.
  - `procedure_input(state, index)` returns the subtask's `ProcedureInvocation`, if it has one.
- `_build_messages` stays in `execution.py` and is passed as `messages` (the image edge case).

**Rationale**: everything that differs per subtask arrives as an argument, so the table can say `Given` with a source. `runtime_handles` is the one function that reads `config["configurable"]` for the derivation. Phase 201 replaces its body with a read of the typed turn services and leaves `derive.py` alone.

## R6. Delegate inheritance (FR-012) and the `extensions` merge

**Decision**: `for_delegate(caller, *, prompt, resume)`. Per field:
- **Inherits**: `session_id`, `memory`, `contacts`, `persona`, `timezone`, `memory_store`, `embed_fn`, `reporter`, `identity_builder`, `abort_token`, `tool_sink` and `script_runner`.
- **`extensions`**: `{**caller.extensions, "_delegate_depth": depth + 1}`.
- **Write gate**: `write_gate` is inherited as one unit, except that `resume` is the child loop (the argument) and `loop_active=False` (the child's own loop sets it).
- **Given**: `prompt`; `messages` is the brief as the only message.
- **Reset**, each with its reason: `model` (the specialist's own model), `token_sink` (the specialist must not stream into the companion's reply), the five prompt notes and `preset`, `active_skills` and `skill_tool_names`, `procedure_guidance`, `procedure_matches` and `procedure_invocation`, `conductor` (depth 1: a specialist cannot delegate, and the companion's deadline stays with the companion), `tool_calls` and `sources` (the delegate merges `sources` upward, as today).

`for_subtask` and `for_unattended` merge `extensions` the same way. A subtask inherits the turn's `extensions` unchanged. An unattended run is given its own (`goal_id`).

**Rationale**: these are the spec's Clarifications answers. `loop_active` is a flag the loop itself sets, so inheriting it would let a specialist call an asks-first tool outside its own loop.

## R7. The child-run outcome and the merge (FR-005, FR-013)

**Decision**:
- `ChildRunOutcome(index, conductor, procedure)` is read from the child context with `outcome_of(ctx, index)`. This runs after a run finishes and also after it parks, because `LoopParked` still leaves the context in hand.
- `_run_with_timeout` returns `(AgentResult | ParkedSubtask, ChildRunOutcome)`.
- `merge_outcomes(state, outcomes, tally)` in `child_runs.py` returns the state updates:
  - `conductor_ledgers` with each run subtask's slot replaced.
  - `conductor_delegate_counts` and `conductor_delegate_total` from the shared tally.
  - `procedure_invocations` merged by subtask.
- `execute_tool` calls `merge_outcomes` once per pass, on both the single and the compound path.
- `record_guided_actions` runs per finished subtask with that subtask's invocation and result. Today only the single path records guided actions.
- `_execute_single` stops writing to `base_ctx`, and `"agent_context"` is no longer in the returned updates.

**Rationale**: this is one value per child and one merge per pass, with no copy-back (FR-005). Sharing the tally makes the caps per turn across concurrent subtasks (FR-013). asyncio is single-threaded, and `run_delegate` has no `await` between the cap check (`delegate.py:248`) and the bump (`:267`), so the check and the bump cannot interleave.

**Two procedure invocations in one turn**: `MessageTrace.procedure` stays one value: the invocation of the lowest subtask index. Each invocation records its own guided actions and is completed with its own subtask's result. A second invocation is logged (`procedure_invocations_extra`), so REST and WS do not change. Phase 208 may widen the trace if it wants.

## R8. Declaring `AgentState` lifetimes (FR-006, FR-007)

**Decision**: `Annotated` markers on each `TypedDict` field, defined in a new `ze_agents/lifetime.py` and re-exported from `ze_sdk.types` so plugins can declare them:
- `Turn(reset=…)` or `Turn(factory=list|dict)`: reset at every turn and every workflow step.
- `Input()`: supplied by whoever starts the turn (`prompt`, `session_id`, `input_modality`, `voice_input`, `image_data`, `image_mime`). The turn reset leaves these alone.
- `Thread(reason)`: kept across turns (`messages`, `last_active_at`).
- `Run(reason)`: kept across the steps of one workflow run and set when the run starts. The reset treats it like `Thread`.

`field_lifetimes(td)` reads `get_type_hints(td, include_extras=True)` on each declaring `TypedDict`, never on the merged class. A field with no marker raises `UndeclaredLifetimeError` (new `ZeError` in `ze_agents/errors.py`), which names the field and its class. `turn_reset(td)` returns `{key: fresh reset value}` for every `Turn` key.

- `build_state_type(plugins)` validates `AgentState` and every extension, so a missing declaration fails graph build, which is startup (US3 scenario 3).
- `make_graph_input(raw, session_id, state_type=AgentState)` returns `{**turn_reset(state_type), **inputs}`.

**Verified**: LangGraph 1.2.2 compiles and runs a `StateGraph` over a merged `TypedDict` whose fields carry a non-callable `Annotated` marker. A dataclass instance is not callable, so LangGraph does not mistake it for a reducer (scratch check, 2026-10-26).

**Alternatives rejected**:
- *A `LIFETIMES` dict next to `AgentState`*: a second list to keep in step, which is today's problem again.
- *Two lifetimes only (turn and thread)*: `session_id` and `prompt` are neither reset nor kept. They are supplied per turn, and a workflow step must not reset `session_id`.

## R9. The workflow step reset (FR-014)

**Decision**:
- `load_workflow_step` (ze-personal) drops its 16-key reset and returns only the step's own keys.
- ze-api's `build_workflow_graph` registers the node through `with_turn_reset(load_workflow_step, state_type)`, a new helper in `ze_core/orchestration/state.py`. The helper returns `{**turn_reset(state_type), **node_output}`.
- `WorkflowAgentState`'s ten fields are declared `Run`.
- The cancel short-circuit (`{"current_step_id": "CANCELLED"}`) also gets the reset. `workflow_cancelled` reads only `Run` fields, so this is harmless.

**Rationale**: a plugin may not import ze-core, and ze-api is the one place that already joins both (`wiring/workflow_graph.py` docstring). Each step now also starts with empty `judgments`, `components`, `tier`, `skill_matches`, conductor state and screen fields (US3 scenario 4).

**Alternative rejected**: put `turn_reset` on `config["configurable"]` for the plugin to call. Phase 201 is removing string-keyed reads, so this would add one.

## R10. Graph input needs the merged state type

**Decision**:
- `Container` gains `state_type: type` (default `AgentState`). Both graph builders set it from `build_state_type(plugins)`: `ze_core/container.py:369` and `ze_api/wiring/container.py:626`.
- `invoke_raw_turn` and `Container.invoke` pass `container.state_type` to `make_graph_input`.
- `begin_workflow_turn(workflow, *, state_type)` gains the argument. ze-api's `wiring/container.py:766` injects it into `configure_workflow_executor` as `functools.partial(begin_workflow_turn, state_type=…)`, so `ze_automation/bootstrap.py` and its `Callable[[Any], dict]` parameter do not change, and ze-automation still never sees ze-core.

**Rationale**: a plugin `Turn` field must be reset in the conversation graph too. Today no plugin declares one (all workflow fields are `Run`), so the generated input is unchanged in practice, but the mechanism is complete. Phase 201 moves `state_type` into the typed turn services. Plan "Seams for 201 and 208" names this.

## R11. The two minimal constructions

**Decision**: `for_action(session_id)` in `derive.py` (kind `action`): every field is `Reset` except `session_id` (`Given`). `BaseAgent.run_undo` and ze-api's `ui_actions._context` call it. `run_action` keeps setting `write_gate.approval_request_id` and `loop_active` on the context it receives.

**Rationale**: the table test covers the minimal kind too (spec Edge Cases), and the grep target of SC-001 shrinks to two places: `fetch_context` and `derive.py`.

## R12. What `for_unattended` gives a goal milestone

**Decision**:

```python
for_unattended(*, session_id, prompt, timezone, memory_store, extensions, pre_approved, resume=None)
```

- `resume` is the `_HeldResume` fields as a `WriteGateState` input.
- `retry_mode=False`.
- Everything else is `Reset`: no prompt notes, skills, procedure state or conductor, and no reporter, sinks or abort token ("no live client: the run is unattended").

**Rationale**: this matches today's milestone context field for field, so behaviour does not change. Phase 214 later routes milestones through the turn pipeline.

## R13. `AgentState.procedure_matches`

**Decision**: delete it (FR-008 as amended). `fetch_context` writes it (`context.py:395`) and nothing reads the state copy. `judgment_state.py:138`, `script_step.py:252` and `procedures/tools.py:45` all read the context's copy. This is a pre-v1 hard cut with no reader to migrate.
