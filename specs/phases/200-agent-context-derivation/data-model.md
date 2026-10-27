# Data Model: AgentContext Derivation

**Phase**: 200 | **Date**: 2026-10-26

No database table changes and no migration. Every type here is an in-process dataclass or `TypedDict`. Types that sit in checkpointed graph state live in `ze_agents/types.py` or `ze_agents/park.py`, which are already on the checkpoint allowlist (`ze_core/checkpoint_serde.py`).

## New parts of `AgentContext` (`ze_agents/types.py`)

### `WriteGateState` (FR-011)

| Field | Type | Was | Notes |
|---|---|---|---|
| `resume` | `ParkedLoop \| None` | `AgentContext.resume` | The parked loop to re-enter |
| `decisions` | `dict[str, WriteDecision]` | `write_decisions` | The user's answers |
| `pre_approved` | `frozenset[str]` | `pre_approved_writes` | Tools allowed to run unasked |
| `round` | `int` | `write_round` | Confirmation rounds answered |
| `approval_request_id` | `str \| None` | `approval_request_id` | The confirmation this run answers |
| `loop_active` | `bool` | `loop_active` | Set only by the agent's own loop; every derivation starts it `False` |
| `retry_mode` | `bool` | `retry_mode` | Retry run: write tools refused |

Accessed as `ctx.write_gate.<field>`. The default is `WriteGateState()`.

### `ConductorState` and `DelegateTally`

| Field | Type | Was | Notes |
|---|---|---|---|
| `hint` | `list[dict[str, str]] \| None` | `conductor_hint` | Routing hint from decompose's conductor rewrite |
| `ledger` | `list[dict[str, str]]` | `conductor_ledger` | This run's ledger: `{agent, status, request_id?}` |
| `tally` | `DelegateTally` | `conductor_delegate_counts`, `conductor_delegate_total` | One object shared by every subtask of a pass |
| `deadline` | `float \| None` | `extensions["_soft_deadline"]` | Run-local; never written to state |
| `stalls` | `dict[str, str]` | `extensions["stall:<agent>"]` | Run-local; never written to state |

`DelegateTally`: `counts: dict[str, int]`, `total: int`. `budget.set_soft_deadline`, `has_budget`, `remaining_seconds` and `exhausted` read and write `ctx.conductor.deadline`. `delegate.py` keeps stall details in `ctx.conductor.stalls`.

### `ProcedureInvocation`

| Field | Type | Was |
|---|---|---|
| `invocation_id` | `str` | `procedure_invocation_id` |
| `procedure_id` | `str` | `procedure_invoked_id` |
| `version_id` | `str` | `procedure_invoked_version_id` |
| `tool_names` | `list[str]` | `procedure_tool_names` (the narrowing, set on invoke) |
| `subtask` | `int` | new: which subtask invoked it (`0` outside a compound turn) |

`AgentContext.procedure_invocation: ProcedureInvocation | None`. `invoke_procedure` (`ze_memory/procedures/tools.py`) sets it. `BaseAgent._visible_tool_names` narrows by `ctx.procedure_invocation.tool_names` when one is set.

## `AgentContext` after this phase: 31 fields and their derivation rules

Rules (R2): **I** inherit · **G** given by the operation's argument (source in brackets) · **R** reset to the default (the reason lives in the table in `derive.py`). The kinds are `subtask` (a routed agent or compound subtask, from the turn context), `delegate` (from the caller's context), `unattended` (a goal milestone, with no parent) and `action` (undo or screen action, with no parent).

| Field | subtask | delegate | unattended | action |
|---|---|---|---|---|
| `session_id` | I | I | G (`goal:<id>`) | G |
| `prompt` | G (subtask prompt) | G (assembled brief) | G (milestone prompt) | R |
| `memory` | I | I | R (no `fetch_context`) | R |
| `contacts` | I | I | R | R |
| `tool_calls` | R (fresh per run) | R | R | R |
| `messages` | G (`_build_messages`) | G (`[brief]`) | R | R |
| `persona` | I | I | R | R |
| `model` | G (`subtask.model`) | R (the specialist's own model) | R | R |
| `reporter` | G (runtime) | I | R (no live client) | R |
| `identity_builder` | G (runtime) | I | R | R |
| `abort_token` | G (runtime) | I | R | R |
| `memory_store` | I | I | G (executor's store) | R |
| `embed_fn` | G (runtime) | I | R | R |
| `token_sink` | G (runtime; single path only) | R (no streaming into the companion's reply) | R | R |
| `tool_sink` | G (runtime) | I | R | R |
| `script_runner` | G (runtime) | I | R (unattended runs have no script runner) | R |
| `sources` | R (merged upward after the run) | R | R | R |
| `screen_context_note` | I | R (the brief carries context, phase 151) | R | R |
| `preset_note` | I | R | R | R |
| `resume_recap` | I | R | R | R |
| `open_priorities_note` | I | R | R | R |
| `preset` | I | R | R | R |
| `active_skills` | I | R (the specialist uses its own tools) | R | R |
| `skill_tool_names` | I | R | R | R |
| `procedure_guidance` | I | R | R | R |
| `procedure_matches` | I | R | R | R |
| `procedure_invocation` | G (state, this subtask) | R | R | R |
| `conductor` | G (state ledger for this subtask, shared tally) | R (depth 1: cannot delegate; the deadline stays with the caller) | R | R |
| `write_gate` | G (turn `retry_mode`, pre-approved union, this subtask's resume inputs) | I as a unit, with `resume` = child loop and `loop_active=False` | G (milestone pre-approved, held resume, `retry_mode=False`) | R (`run_action` sets the request id and `loop_active`) |
| `extensions` | I (copy) | I (merged with `_delegate_depth`) | G (`goal_id`) | R |
| `timezone` | I | I | G (application settings) | R |

Removed from `AgentContext`: the 15 flat fields now held by the three parts. `fetch_context` no longer sets conductor fields on the turn context (R4).

## `AgentState` lifetimes (`ze_core/orchestration/state.py`)

Markers (R8): **Input** (supplied by the turn's caller) · **Turn(reset)** · **Thread** · **Run**.

| Key | Lifetime | Reset value | Change |
|---|---|---|---|
| `prompt`, `session_id`, `input_modality`, `voice_input`, `image_data`, `image_mime` | Input | — | |
| `image_caption`, `envelope`, `memory_context`, `agent_context`, `agent_result`, `budget_status`, `write_confirmation`, `final_response`, `error`, `conductor_hint`, `routing_hints`, `screen_note`, `screen_trace`, `screen_subject_line`, `message_trace`, `tier`, `skill_matches` | Turn | `None` | |
| `subtask_results`, `completed_subtask_indexes`, `parked_subtasks`, `write_decisions`, `write_outcomes`, `components`, `preset_components`, `correlations`, `judgments` | Turn | `[]` | |
| `blocked`, `budget_approved` | Turn | `False` | |
| `write_rounds`, `conductor_delegate_total` | Turn | `0` | |
| `conductor_delegate_counts` | Turn | `{}` | |
| `resume_recap_applied`, `open_items_query` | Turn | `False` | newly reset (FR-008) |
| `loop_offer_ids`, `pre_approved_writes` | Turn | `[]` | newly reset (FR-008) |
| `conductor_ledgers` | Turn | `[]` | renamed from `conductor_ledger`; one ledger per subtask index. A missing slot reads as `[]`; the merge pads before assigning |
| `procedure_invocations` | Turn | `[]` | new; `list[ProcedureInvocation]` by subtask |
| `messages`, `last_active_at` | Thread | — | |
| ~~`procedure_matches`~~ | — | — | deleted (R13) |

`WorkflowAgentState` (`ze_personal/graph/workflow.py`): all ten fields (`workflow_id`, `workflow_execution_id`, `workflow_steps`, `current_step_id`, `steps_by_id`, `visit_counts`, `workflow_step_results`, `step_started_at`, `step_attempt`, `from_retry`) are **Run**.

## Runtime and outcome types (`ze_agents/derive.py`)

- `RuntimeHandles` (frozen): `reporter`, `identity_builder`, `abort_token`, `embed_fn`, `token_sink`, `tool_sink`, `script_runner`. These are never checkpointed. ze-core builds them in `child_runs.runtime_handles(config, stream=…)`.
- `ChildRunOutcome` (frozen): `index: int`, `conductor: ConductorState`, `procedure: ProcedureInvocation | None`. It is read by `outcome_of(ctx, index)`, also after a park.
- `FieldRule`: `subtask`, `delegate`, `unattended`, `action`, each an `Inherit`, `Given(source: str)` or `Reset(reason: str)`.

## State transitions: conductor state across a pause (US2 scenario 3)

1. Routing (decompose rewrite) sets `conductor_hint` and `conductor_ledgers=[[{agent, "planned"}…]]`.
2. `execute_tool`, pass 1: one `DelegateTally` comes from the state. Each run subtask gets `ConductorState(hint, copy(ledgers[i]), tally)`. The companion delegates, which bumps the tally, and the specialist parks. Ledger entry: `awaiting_confirmation`.
3. `merge_outcomes` writes `ledgers[i]`, counts and total to state. The pass ends parked.
4. `await_write_confirmation` records the decisions.
5. `execute_tool`, pass 2: the same derivation runs from state. The resumed delegate does not bump (`resume is not None`) and moves the in-flight entry to `done`. The merge writes the ledger back. The total stays at 1, and the entry appears once.
