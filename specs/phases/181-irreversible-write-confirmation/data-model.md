# Data Model: Irreversible Write Confirmation (181)

## Tool declaration (`ze_agents/tool.py`, `ToolSpec`)

| Field | Type | Rule |
|---|---|---|
| `reversibility` | `ToolReversibility \| None` | unchanged (165) |
| `asks_first` | `bool \| None` | WRITE + IRREVERSIBLE: `None` → resolved `True`; `False` requires `no_ask_reason`. REVERSIBLE / READ: must be `None`. |
| `no_ask_reason` | `str \| None` | non-empty iff `asks_first is False` |
| `ask_check` | `Callable[[dict, AgentContext], AskDecision] \| None` | optional pre-call check; must not run the tool. Allowed on any WRITE tool (REVERSIBLE `create_workflow`/`create_goal` use it, R7). |
| `constraint_gate` | `bool` | unchanged (144); evaluated on the call path before parking (R5) |
| `editable_field` | `str \| None` | the argument the user may edit in the confirmation (e.g. `send_email` → `body`); replaces `_apply_edited_content`'s name switch |
| `summarize` | `Callable[[dict], str] \| None` | short argument summary for the item; defaults to `constraint_describe` when present, else a generic `key: value` summary truncated to 160 chars |

`AskDecision`: `RUN` \| `ASK(reason: str = "")` \| `REFUSE(message: str)`.

Resolution order in `call_tool` (first match wins). The constraint veto runs before any approval or pre-approval can let a call through (amended 2026-10-16, Plumb B2):
1. `ctx.retry_mode` and WRITE → refused (165, unchanged).
2. constraint veto (constraint-gated tools), on every other WRITE call, approved and pre-approved ones included: VETO → refuse (gate `refused`), whatever the approval.
3. `_approval` (an `ApprovedCall` built only by the resume path from park state, never from model args) → run, outcome `approved`. A CONFIRM-level conflict is not asked again: the user saw it on the item.
4. constraint veto CONFIRM(text) on a call that is not approved → park with `conflict=text`, even when the tool opted out or is pre-approved. In an unattended run that park becomes a hold (FR-025).
5. tool in `ctx.pre_approved_writes` (unattended step) → run, outcome `pre_approved`.
6. `ask_check` result if declared: ASK → park; REFUSE → refuse; RUN → run.
7. `asks_first` resolved `True` → park.
8. run.

Why the veto re-checks an approved call: an unattended hold can be approved up to 24 hours after it parked, and an approve can carry edits (a new email body). A hard VETO that matches the call as it will run still refuses it.

A park on the 4th confirmation round of a turn (`ctx.write_round >= 3`) is converted to a refusal: result "This needs the user's approval; ask them in your reply instead.", outcome `refused_over_cap`.

Registration errors (`AgentConfigError`): `asks_first=False` without reason; reason without `asks_first=False`; `asks_first` on REVERSIBLE or READ; `editable_field` not in the tool's parameters.

## Park types (`ze_agents/park.py`, all JSON-safe dataclasses, in the checkpoint serde allow-list)

**ParkedWrite**
- `item_id: str` (uuid4), `call_id: str` (the model's tool call id), `tool: str`, `args: dict` (the model's arguments only, `_lm_args`; injected dependencies such as stores and clients are never saved and are re-merged by `_merge_deps` when the approved call runs), `effect_phrase: str`, `summary: str`, `editable_field: str | None`, `conflict: str | None`, `reason: "asks_first" | "constraint" | "check"`, `agent: str`.

**ParkedLoop**
- `agent: str`
- `messages: list[dict]` — transcript up to and including the assistant tool-call message and the tool messages of calls that ran
- `accumulated: list[ToolCall]` — tool calls made so far in this loop
- `iteration: int`
- `parked: list[ParkedWrite]` — in model order
- `child: ParkedLoop | None` — set when this loop waits on a delegate whose specialist parked
- `child_call_id: str | None`, `child_arguments: dict | None` — the delegate call to re-enter

Invariant: exactly one of `parked` non-empty or `child` set may be true per response, or both (a response with a direct asks-first call and a delegate that parked); items from `child` are collected recursively for display.

**ParkedSubtask**: `index: int` (0 for single turns), `loop: ParkedLoop`.

**WriteDecision**: `item_id: str`, `outcome: "approved" | "edited" | "denied" | "timed_out" | "superseded" | "duplicate"`, `edited_text: str | None`. `duplicate` is given to an alias whose shown item was approved or edited: the resumed loop gets `DUPLICATE_RESULT` (gate `duplicate`) and the call does not run a second time.

**WriteConfirmation** (graph interrupt payload and trace record)
- `request_id: str`, `kind: "write" | "budget" | "held"`, `round: int` (1–3), `items: list[ConfirmItem]`, `status: "open" | "approved" | "denied" | "timed_out" | "superseded"`, `aliases: dict[str, str]`.
- One item per distinct `(tool, args)`. A parked call identical to a shown one (e.g. two subtasks to the same agent) is not shown; `aliases` maps its `item_id` to the shown item's, and it takes that item's answer (approve → `duplicate`).
- `ConfirmItem`: `item_id`, `agent`, `tool`, `effect_phrase`, `summary`, `editable_field`, `proposed_text` (current value of the editable field), `conflict`.

**LoopParked** (`ze_agents/errors.py`, `ZeError` subclass): carries one `ParkedLoop`. Raised only by `agentic_loop`; caught by `run_delegate`, `_run_with_timeout`, `GoalExecutor`.

## AgentContext (`ze_agents/types.py`)

Removed: `intent`, `gate_decision`, `evaluate_delegate`.
Added: `resume: ParkedLoop | None`, `write_decisions: dict[str, WriteDecision]` (by `item_id`), `approved_call_ids: set[str]` (derived on resume), `pre_approved_writes: frozenset[str]`, `write_round: int`, `loop_active: bool` (set by `agentic_loop` while it runs; `call_tool` on an asks-first tool with `loop_active` false raises `AgentConfigError`).

## ToolCall (`ze_agents/types.py`)

Removed: `is_draft`. Added: `parked: ParkedWrite | None`, `child_loop: ParkedLoop | None` (delegate only), `approval: dict | None` (`{request_id, outcome}` for approved/edited calls, `{outcome: "pre_approved"}` for unattended pre-approval; published to `ze_agents.park.current_approval` (a ContextVar) while the approved call runs; `ActionRecorder` reads it and adds `CausalRef(kind="approval", id=request_id)` to the action record, FR-030). `gate` gains values: `"approved"` (user approved), `"pre_approved"`, `"denied"`, `"refused_over_cap"`, `"none"`.

## AgentState (`ze_core/orchestration/state.py`)

Removed: `session_overrides`, `gate_decision`, `subtask_gate_decisions`, `pending_subtask_awaits`, `approved_subtask_indexes`, `denied_subtask_indexes`, `pending_confirmation`, `approved_agents`.
Added:
- `blocked: bool` — set by `preflight` when the routed agent is disabled
- `budget_status: Any | None` (kept), `budget_approved: bool`
- `parked_subtasks: list[ParkedSubtask]`
- `write_confirmation: WriteConfirmation | None` — the open one
- `write_decisions: list[WriteDecision]` — answers to the open one
- `write_rounds: int` — confirmations opened this turn
- `write_outcomes: list[dict]` — per item, every round: `{request_id, round, item_id, agent, tool, summary, outcome}`; copied to `MessageTrace.write_confirmations`
`subtask_results` and `completed_subtask_indexes` stay (158 shape, now also used by single turns as index 0).

## Routing (`ze_core/routing/types.py`)

`SubTask`: remove `intent`; add `changes: bool = False` (set only by the fallback decomposer; read only by 155 `is_mixed_gather_act`). `conductor_hint` entries: `{agent, prompt, changes}`.

## MessageTrace (`ze_core` trace types)

Add `write_confirmations: list[dict]` (= `write_outcomes`). `record_trace` stops reading `approved_agents`: a call's "confirmed" flag in `_extract_tool_calls` becomes `ToolCall.gate in ("approved", "pre_approved")`, which retry eligibility (165/180) keeps reading. The web trace panel renders a "Confirmations" section.

## Automation

- `WorkflowStep`: remove `intent`; add `approved_writes: list[str] = []` (inside `workflows.steps` JSONB; no migration). `planned_writes: list[str]` is stored on the step too: the asks-first tools the planner (or the REST caller) names for it. `planned_writes(step)` returns the named tools that the step's agent really has (asks-first tools of `get_agent_class(step.agent_hint).tools`); a step that names none plans no writes (e2e finding 4, 5e677605). Approving the plan grants exactly `planned_writes(step)`; any other asks-first call in that step holds at run time.
- `Milestone`: remove `intent`; add `approved_writes: list[str]` and `planned_writes: list[str]` (same rule as steps); `MilestoneStatus` gains `HELD = "held"`.
- `WorkflowExecution` status gains `held`: the `workflow_executions_status_check` constraint (last set in `zc025`) is replaced to allow `pending, running, completed, failed, cancelled, held`.

## Tables

**Migration `zc034_drop_capability_overrides`** (renumbered from zc032 when main's Phase 180 took zc032 for `messages.rollback`; chain zc031 → zc032 (180) → zc033 → zc034) (ze-core, `core/engine/ze-core/ze_core/migrations/versions/`): `DROP TABLE capability_overrides`. Downgrade recreates it as in `004`.

**Migration `zc033_write_confirmation`** (ze-automation, linear after zc032):
- `ALTER TABLE goal_milestones DROP COLUMN intent, ADD COLUMN approved_writes TEXT[] NOT NULL DEFAULT '{}'`
- `ALTER TABLE workflow_executions DROP CONSTRAINT workflow_executions_status_check, ADD CONSTRAINT workflow_executions_status_check CHECK (status IN ('pending','running','completed','failed','cancelled','held'))`
- `CREATE TABLE held_writes (request_id TEXT PRIMARY KEY, source TEXT NOT NULL /* workflow | goal */, owner_ref TEXT NOT NULL /* workflow execution id | milestone id */, items JSONB NOT NULL, payload JSONB NOT NULL /* graph config for workflows; ParkedLoop for goals */, status TEXT NOT NULL DEFAULT 'open', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), expires_at TIMESTAMPTZ NOT NULL, decided_at TIMESTAMPTZ)`, index on `(status, expires_at)`.
- Owner: `ze_automation/holds/store.py` `PostgresHeldWriteStore` (Protocol `HeldWriteStore`). Added to the AGENTS.md migration table under ze-automation.

`pending_confirmations` (zc027) keeps its columns; `actions` JSONB now stores `{kind, round, items}` (`kind` is `"write"` or `"budget"`; `items` is the frame's item list), so a replay or a superseding turn can rebuild the frame and the trace rows from the row alone.

## State transitions

Write confirmation: `open → approved | denied | timed_out | superseded`. Each terminal state writes one `write_outcomes` row per item.

Held write: `open → approved | denied | expired`. `approved` resumes the workflow graph (`Command(resume=…)`) or the goal milestone loop; `denied`/`expired` resume with `timeout`/`denied` decisions.

Milestone: `in_progress → held → in_progress` (on answer) `→ completed | failed`.
