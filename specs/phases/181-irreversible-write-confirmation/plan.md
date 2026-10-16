# Implementation Plan: Irreversible Write Confirmation

**Branch**: `181-irreversible-write-confirmation` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/phases/181-irreversible-write-confirmation/spec.md` (scope Q1–Q10 and clarify C1–C5 answered by the user on 2026-10-15). Research: [research.md](research.md). Data model: [data-model.md](data-model.md). Contracts: [contracts/](contracts/). Validation: [quickstart.md](quickstart.md).

## Dependencies and merge order

| Phase / floor | State on 2026-10-15 | What 181 needs | Rule |
|---|---|---|---|
| 165 reversibility, 180 retry rollback | on `main` | `ToolReversibility`, `effect_phrase`, `retry_mode`, retry eligibility from trace effect metadata | none |
| **171 Follow-ups** (Cobble) goal-local confirmation | branch `171-follow-ups`, not on `main` | touches `goals/tools.py`, `base_agent.py` (`call_tool`'s `ToolConfirmationRequired` branch), `execution.py` (`tool_interrupts`, `confirmed`) | **Soft.** If it lands first, T001 re-reads its diff and the hard-cut tasks delete its additions (FR-028). If it has not landed when 181 starts, 181 proceeds from `main` and the Maestro asks Cobble to drop the goal-confirmation part. The two must not both land with a live `ToolConfirmationRequired`. |
| Other open floors | `legacy-table-reads` touches no 181 file | — | — |

## Summary

1. **Declaration** (ze-agents): `ToolSpec` gains `asks_first`, `no_ask_reason`, `ask_check`, `editable_field`, `summarize`; registration enforces the rules; the 35-row audit is applied in each owning package; `pause_goal`/`resume_goal` become a REVERSIBLE pair.
2. **Park** (ze-agents): `call_tool` resolves RUN / PARK / REFUSE in a fixed order (data-model); `agentic_loop` raises `LoopParked(ParkedLoop)` after the response whose calls parked; `run_delegate` turns a specialist's park into a parked delegate call, so the conductor parks behind it.
3. **Pause and resume** (ze-core): `capability_check` → `preflight` (disabled agent, budget pause); `_run_with_timeout` catches `LoopParked` (no interrupt below the node); `execute_tool` stores `parked_subtasks`; a new node `await_write_confirmation` whose first statement is `interrupt()`; resume re-enters `agent.run()` with `ctx.resume`, runs exactly the approved calls before any model call, then continues; max 3 rounds; deny/timeout = declined results + code-guaranteed "Okay, I didn't …" lines; supersede as today.
4. **Composition**: the 144 veto is evaluated in `call_tool` (CONFIRM parks with the conflict text, VETO refuses); the 113 budget is its own pre-execution pause; a retry never parks; WorkspaceGate becomes `workspace_ask_check`.
5. **Transport** (ze-api, ze-client, ze-web): `confirm_request` with `kind` + `items[]`, `confirm` with `edits`; timeout resumes as a deny; trace `write_confirmations`; web confirmation card with approve all / deny all / edit; a trace panel section.
6. **Unattended** (ze-automation, ze-api, ze-web): per-step `approved_writes`; plan creation/edit asks with the planned writes listed; the workflow graph and the goal executor hold un-pre-approved calls as `held_writes` (24 h) and push via the governor (`write_approval_held`, requested class); answers via REST, notification or chat replay; `HeldWriteExpiryJob`.
7. **Hard cut**: delete `Intent`, `Mode`, `GateDecision`, `intents`, `default_mode`, `_primary_intent`, `SubTask.intent` (→ `SubTask.changes` for 155), `CapabilityGate`, `capability_overrides` (`zc032`), capabilities REST + WS command + web button, `session_overrides`, `draft_response`/`await_confirmation`/`await_subtask_confirmation` with their edges and state, the 152 delegate gate, `ToolConfirmationRequired`, `tool_interrupt_fn`, `workspace_confirmed`, `ToolCall.is_draft`, `AgentContext.intent/gate_decision/evaluate_delegate`, `RetrievalRequest.intent`, `WorkflowStep.intent`, `Milestone.intent` (`zc033`).
8. **Evals**: `POST /api/v0/eval/confirm`, a `confirm:` scenario step, `eval/scenarios/write_confirmation.yaml`.

**Plan decision flagged to the user** (not covered by Q1–Q10/C1–C5): Q5 deletes `SubTask.intent`, but 155's mixed gather+act rewrite needs a gather/act label. The fallback decomposer emits `"changes": true|false` per subtask instead of an intent (`SubTask.changes`), read only by `is_mixed_gather_act`. It is a routing label, not a gate. The alternative (rewrite every multi-agent compound turn to the conductor) changes 155/158 behaviour and is out of scope.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript + React (ze-web).

**Primary Dependencies**: existing only — LangGraph (`interrupt`, `Command`, `AsyncPostgresSaver`), asyncpg, FastAPI. No new packages.

**Storage**: migrations `zc034_drop_capability_overrides` (ze-core) and `zc033_write_confirmation` (ze-automation: `goal_milestones` drops `intent` and adds `approved_writes`; `workflow_executions` status check gains `held`; new `held_writes`). `pending_confirmations` unchanged (its `actions` JSONB stores the items). `workflows.steps` JSONB gains `approved_writes` per step, no DDL.

**Testing**: pytest with a mocked LLM (`complete_with_tools` scripted per iteration) and `AsyncMock` pools; the real checkpoint serde in the restart test; `@pytest.mark.pg` for `held_writes` and `zc033`; vitest for the confirmation card and trace section; eval scenarios against `make dev-eval`.

**Target Platform**: the single-user Ze server (uvicorn) + ze-web SPA.

**Project Type**: monorepo web service + SPA.

**Performance Goals**: parking adds no model call. Resume adds one checkpoint read and re-runs `agent.run()` setup (system prompt build); no model call happens before the approved tools run.

**Constraints**:
- No `interrupt()` below a graph node: after this phase `langgraph.types.interrupt` is called only by `await_write_confirmation` and `await_budget_confirmation` (a test asserts the import sites).
- `ze_agents` gains no `ze_core` or `ze_memory` import; park types live in `ze_agents`.
- Plugins never import `ze_core`; `ze_sdk.types` drops `Mode`/`Intent` and adds `AskDecision`.
- The workflow graph is composed in `apps/ze-api/ze_api/workflow_graph.py`; its edges live there and in `plugins/ze-personal/ze_personal/graph/workflow.py` (`after_capability_check_workflow` → `after_preflight_workflow`).
- Doctrine functions served: **Action** (tools act only with consent) and **Governance** (the rule is enforced in code on every path; approvals and outcomes are on the trace).

**Scale/Scope**: 35 IRREVERSIBLE tools across 11 packages; 13 agent classes lose `intents`; about 17 source files reference `GateDecision` and 11 reference `CapabilityGate`; about 40 test files change.

## Blast radius

`graphify affected --depth 2` on the ground graph (2026-10-15), plus grep where graphify had no unique node:

| Symbol | Non-test packages affected |
|---|---|
| `Mode` / `Intent` (51 nodes) | ze-api, ze-priority, ze-automation, ze-worldstate, ze-agents, ze-plugin, ze-core, ze-ingestion, ze-sdk, ze-calendar, ze-finance, ze-messenger, ze-news, ze-personal, ze-prospecting |
| `ToolConfirmationRequired` (50) | the same set + ze-workspace |
| `run_delegate` (75) | every agent package (through `agentic_loop`) |
| `RetrievalRequest` (100) | ze-memory + every agent package (field removal only) |
| `capability_check` (24), `draft_response` (11), `await_confirmation` (10), `await_subtask_confirmation` (9), `_execute_compound` (19), `_run_with_timeout` (13), `bind_delegate_evaluator` (5) | ze-core (+ ze-api `workflow_graph.py` by node names) |
| `is_mixed_gather_act` (13), `apply_conductor_rewrite` (24) | ze-core |
| `handle_confirm` (33), `send_confirmation_request` (36) | ze-api |
| `SpendBudgetChecker` (29) | ze-api, ze-core |
| `WorkspaceGate` (28) | ze-api, ze-automation, ze-workspace |
| grep | `GateDecision` 17 src / 19 test files; `CapabilityGate`/`capability_gate` 11 / 10; `session_overrides` 5 / 5; `tool_interrupt_fn` 5 / 3; `intents = {` 13 agent classes; web: `ChatWorkspace.tsx` (capabilities button), `features/respond-to-confirmation`, `widgets/trace-panel` |

Engineers run `graphify update .` on the floor and `graphify affected` before changing each signature (AGENTS.md rule).

## Design

### D1. Resolution in `call_tool` (`ze_agents/base_agent.py`)

The order is in [data-model.md](data-model.md). A park returns `ToolCall(parked=ParkedWrite(...), success=False, gate="parked")` and runs no `on_tool_start` hook except the call check (D4). `call_tool(..., _approved_call_id=…)` is the resume entry; it skips steps 3–6 and runs hooks normally.

### D2. Park and resume in `agentic_loop`

- After the per-response dispatch loop, collect parked `ToolCall`s (direct and delegate). If any, raise `LoopParked(ParkedLoop(agent=self.name, messages=messages, accumulated=accumulated, iteration=iteration, parked=[...], child=..., child_call_id=..., child_arguments=...))`.
- At loop start, if `ctx.resume` is set and `ctx.resume.agent == self.name`: `messages[:] = resume.messages`, `accumulated = list(resume.accumulated)`, start at `resume.iteration + 1`. Then the resume step: each `ParkedWrite` approved/edited → `call_tool(..., _approved_call_id=pw.call_id, **args)` (edited: `args[editable_field] = text`); denied/timed_out/superseded → `ToolCall(gate="denied", result=DECLINED_RESULT)`; append the tool message for `pw.call_id`. If `resume.child`: `run_delegate(resume.child_arguments, ctx, …, resume=resume.child)` → tool message for `child_call_id` (a `LoopParked` from it re-parks this loop with the new child). Clear `ctx.resume` before continuing.
- `ctx.loop_active = True` while the loop runs, so a direct asks-first call outside it fails loudly.
- `max_iterations` counts across the park (resume continues the counter).

### D3. Graph (ze-core)

```
preprocess → embed_route → (decompose) → fetch_context → match_skills → preflight
preflight → execute_tool | await_budget_confirmation | end_blocked
await_budget_confirmation → execute_tool | record_trace (denied)
execute_tool → await_write_confirmation (new park, round ≤ 3) | correlate
await_write_confirmation → execute_tool
correlate → surface_loops → synthesize | record_trace → write_memory → END
```

- `preflight`: `blocked` when a routed agent is disabled (today's `enabled=False` → BLOCKED); the budget check (113) unless `retry_mode` or `budget_approved`.
- `execute_tool`: single turns use the compound bookkeeping with index 0; `to_run` = subtasks not completed and either not parked, or parked with decisions; `_run_with_timeout` returns `AgentResult | ParkedSubtask`; finished results merge into `subtask_results`/`completed_subtask_indexes` (158 shape); parked ones go to `parked_subtasks`. On a new park it builds the `WriteConfirmation` (items flattened from each loop and its children, `round = write_rounds + 1`, `request_id = uuid4()`). It records the answered round's outcomes into `write_outcomes`.
- `await_write_confirmation`: `resume = interrupt(confirmation)` is its first statement; maps `{choice, edits}` or `{choice: "timeout"}` to `WriteDecision`s; sets `write_decisions` and `write_rounds += 1`.
- Deny guarantee: a pure helper `ensure_declined_lines(reply, outcomes)` appends "Okay, I didn't <imperative effect>." for each denied or timed-out item whose imperative phrase is not already in the reply (case-insensitive). It runs once, in `record_trace`'s input path, before the reply is saved. `effect_imperative` (contracts/ws-confirmation.md) gives the base form used by both the card and this line.
- The graph compiles with **no** `interrupt_before`; the two pause nodes call `interrupt()`.
- Workflow graph (`workflow_graph.py`): the same `preflight` → `execute_tool` → `await_write_confirmation` wiring; `after_preflight_workflow` fails the step only when blocked.

### D4. Constraint veto (`ze_memory/constraint_veto.py`)

Extract the matching into a pure `evaluate(event) -> VetoOutcome` (same `_facts_for` cache). ze-agents adds an optional `HarnessHook.check_call(event) -> AskDecision` (default `RUN`); `call_tool` calls it on every registered hook for `constraint_gate` tools before parking. `ConstraintVetoHook.check_call` returns `REFUSE(payload)` for VETO, `ASK(text)` for CONFIRM, `RUN` for ALLOW. Its `on_tool_start` interrupt branch is deleted. ze-agents does not import ze-memory.

### D5. Transport (ze-api)

- `turn.py`: the turn outcome carries `confirmation: WriteConfirmation | None` (the interrupt payload) instead of `draft`/`confirm_*`; `_confirmation_meta` is deleted.
- `websocket/confirmation.py`: `send_confirmation_request` builds the frame from `outcome.confirmation` (contract) and saves `pending_confirmations(actions=items)`. `handle_confirm` validates `edits`, resumes with `{"choice", "edits"}` for both approve and deny (no more `abort_pending_checkpoint` on deny), and routes held request ids to `HeldWriteResumer`. `confirmation_timeout` resumes with `{"choice": "timeout"}` and delivers the reply with `send_with_thread` (push when offline).
- `turns.py` supersede: clearing as today; the superseding turn's trace gets `superseded` outcomes for the cleared request's items (read from the stale checkpoint's `write_confirmation`).
- Deleted: the `/capabilities` WS command (`commands.py`), `routes/capabilities.py`, `dependencies.get_capability_gate`, the `capabilities` OpenAPI tag; `testing.py` `make_gate` is rewritten without intents.

### D6. Unattended (ze-automation + ze-api)

- `planned_writes(step)` (ze-automation; uses `ze_agents.registry` + `ze_agents.tool`) and a `plan_writes_check` `ask_check` on `create_workflow`, `create_goal` and `edit_workflow_steps`: ASK with the per-step list when it is non-empty. The item summary lists "Step 2 (messenger) may: send an email, archive an email". After the approved call runs, the tool writes `approved_writes` for those steps. `edit_workflow_steps` clears `approved_writes` of changed steps and re-grants them on approval.
- Workflow runner (`bootstrap.py`): passes `pre_approved_writes` per step through `config["configurable"]`. After `ainvoke`, if the graph is paused at `await_write_confirmation`, it creates the `held_writes` row (payload = run config), sets the execution `held`, and pushes `write_approval_held`. `HeldWriteResumer.resume(request_id, decision)` → `workflow_graph.ainvoke(Command(resume=…), config)` and continues the runner loop.
- Goal executor: catches `LoopParked` around `agent.run(ctx)`; the milestone goes `held`; the `held_writes` payload is the serialised `ParkedLoop` + milestone id; push. Resume rebuilds the milestone context with `resume=ParkedLoop` and the decisions, calls `agent.run` again, and continues the milestone as today.
- `PushKind("write_approval_held")` (requested class, normal urgency, buzz) in `ze_automation/push_kinds.py`; title "<source name> needs your OK", body the first item's imperative effect + summary, deep link `/?confirm=<request_id>`.
- REST (contracts/rest.md): routes in a new `apps/ze-api/ze_api/api/routes/held_writes.py` calling query functions in `ze_automation/rest.py`; the workflow step `PATCH` gains `approve_writes` and `writes_needing_approval`. `HeldWriteExpiryJob` runs hourly and resumes expired holds with `timeout`.
- Action records (135/136): `call_tool(_approved_call_id=…)` sets `ToolCall.approval = {request_id, outcome}` (or `{outcome: "pre_approved"}`); the shared action-record submit path in `ze_agents` (the 136 helper producers call) copies it into the record's evidence, so every executed asks-first call cites its approval (FR-030).
- The notification row for the push carries the request id; the web card answers through `decideHeldWrite`.

### D7. ze-web

- `entities/confirmation` (new): types from `@myguyze/ze-client`, `useHeldWritesQuery`, `useDecideHeldWriteMutation`.
- `features/respond-to-confirmation`: `useConfirmation` handles the items frame and sends `{choice, edits}`; a `ConfirmationCard` (items with effect, summary and conflict badge; inline textarea for editable items; Approve all / Deny all).
- `widgets/chat-workspace`: renders the card in place of today's prompt/approve/cancel rendering; the capabilities command button is removed.
- `widgets/notification-bell`: held-write notifications open the card (answers via REST).
- `widgets/trace-panel`: a "Confirmations" section from `trace.write_confirmations`.
- The `?confirm=<request_id>` route param opens the matching card.

### D8. Hard-cut ordering inside the phase

The deletions land in this phase. They are sequenced so each task leaves the suite green: the new path is built beside the old edges inside one lane, the graph is switched, then the old path is deleted (US7 tasks). Nothing transitional survives the phase (Principle VIII allows in-tree transitional code deleted in the same phase).

## Constitution Check

*Pre-design and post-design: PASS.*

- **I. Spec-First**: spec, clarifications, plan, research and contracts exist before code. PASS.
- **II. Single-User**: no user scoping; held writes are global rows. PASS.
- **III. Layered Architecture**: the rule and park types live in ze-agents (contracts); the graph in ze-core; the veto stays in ze-memory and plugs in through the hook interface (no ze-agents → ze-memory edge); holds live in ze-automation; plugins only change `@tool` declarations through `ze_sdk`. PASS.
- **IV. Typed Python**: dataclasses in `ze_agents/park.py`; `LoopParked` is a `ZeError` subclass; Pydantic only in `ze_api/api/schemas.py`. PASS.
- **V. Tests**: per-package tests (quickstart); pg tests for the new table. PASS.
- **VI. Persistence**: raw-SQL Alembic `zc034` (ze-core owns `capability_overrides`; renumbered after Phase 180's zc032), `zc033` (ze-automation owns the goal/workflow stores and the new table). PASS.
- **VII. One gateway**: no new model calls. PASS.
- **VIII. Hard cuts**: every replaced surface is deleted in this phase (D8); no shim and no dual frame shape. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/phases/181-irreversible-write-confirmation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── tool-declaration.md
│   ├── ws-confirmation.md
│   └── rest.md
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (touched)

```text
core/contracts/ze-agents/ze_agents/
├── park.py                  # NEW: park types, effect_imperative, ensure_declined_lines
├── tool.py                  # asks_first, no_ask_reason, ask_check, editable_field, summarize; AskDecision
├── base_agent.py            # call_tool resolution; agentic_loop park/resume; DRAFT + ToolConfirmationRequired branches deleted
├── delegate.py              # park propagation; resume=; delegate gate + intent argument deleted
├── hooks.py                 # optional check_call()
├── types.py                 # AgentContext / ToolCall / RetrievalRequest fields; Mode, Intent, GateDecision deleted
├── errors.py                # LoopParked; ToolConfirmationRequired deleted
└── interrupt.py             # DELETED
core/engine/ze-core/ze_core/
├── orchestration/{graph.py,edges.py,state.py}
├── orchestration/nodes/{execution.py,trace.py,context.py,routing.py}
├── routing/{router.py,complexity.py,fallback.py,types.py}
├── capability/              # DELETED (budget checker already lives in telemetry/budget.py)
├── conversation/turn.py
├── container.py, bootstrap.py
└── migrations/versions/zc034_drop_capability_overrides.py   # NEW
core/cognition/ze-memory/ze_memory/constraint_veto.py
core/ops/ze-workspace/ze_workspace/{tools.py,gate.py}
core/automation/ze-automation/ze_automation/
├── holds/{__init__.py,types.py,store.py,resumer.py}        # NEW
├── jobs/held_write_expiry.py                               # NEW
├── agents/{goals,workflow}/{agent.py,tools.py}
├── goals/{types.py,executor.py,postgres.py}
├── workflow/{types.py,postgres.py,planner.py,validation.py}
├── bootstrap.py, rest.py, push_kinds.py
└── migrations/versions/zc033_write_confirmation.py         # NEW
core/cognition/ze-worldstate, core/arbitration/ze-priority, core/ops/ze-ingestion   # agent intents + tool declarations
plugins/{ze-calendar,ze-messenger,ze-personal,ze-finance,ze-prospecting,ze-news}     # agent intents + tool declarations
plugins/ze-personal/ze_personal/graph/workflow.py
packages/ze-sdk/ze_sdk/{types.py,__init__.py}
apps/ze-api/ze_api/
├── api/websocket/{confirmation.py,turns.py,commands.py}
├── api/routes/{capabilities.py (DELETED),eval.py,__init__.py}, api/{schemas.py,openapi.py,dependencies.py,app.py}
├── workflow_graph.py, container.py, testing.py, compose.py
packages/ze-client/src/generated/*                           # regenerated
apps/ze-web/src/{entities/confirmation,features/respond-to-confirmation,widgets/chat-workspace,widgets/notification-bell,widgets/trace-panel}
core/ops/ze-eval/ze_eval/{runner.py,judge.py}, eval/scenarios/write_confirmation.yaml
```

**Structure Decision**: the existing monorepo layout; one new subpackage, `ze_automation/holds/`.

## Complexity Tracking

No constitution violations. The phase is large; tasks.md splits it into lanes so the new path and the hard cut land together.
