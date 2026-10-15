# Research: Irreversible Write Confirmation (181)

All findings are verified against `main` @489f348e and the `171-follow-ups` branch on 2026-10-15. Paths are repo-relative.

## R1. Where tools run today, and where they pause

| Path | Entry | How a write is gated today | Pause site |
|---|---|---|---|
| Single turn | `execute_tool` → `_execute_single` → `_run_with_timeout` → `agent.run()` → `BaseAgent.agentic_loop` → `call_tool` | `capability_check` maps (agent, `_primary_intent`) to a `GateDecision`; `CONFIRM` goes `draft_response` → `await_confirmation` (`interrupt_before`) → `execute_tool` **re-runs the agent** | graph node (safe), but approved ≠ executed |
| Compound (parallel) | `_execute_compound` → `asyncio.gather(_run_with_timeout…)` | 158 per-subtask decisions; `await_subtask_confirmation` node interrupts before a subtask runs | graph node (safe) for the per-subtask gate; **tool-level** interrupts inside gather are unsafe (Vigil) |
| Conductor | companion `agentic_loop` → `run_delegate` (`ze_agents/delegate.py`) → specialist `run()` | 152 `ctx.evaluate_delegate(agent, intent)`; `AWAIT_CONFIRMATION` calls `tool_interrupt_fn` **inside the companion's loop** | in-loop interrupt (unsafe: the node re-runs on resume) |
| Workspace | `workspace_*` tool body → `_confirm()` raises `ToolConfirmationRequired`; `call_tool` catches and calls `tool_interrupt_fn` | WorkspaceGate (action × origin) | in-tool interrupt (unsafe) |
| Constraint veto (144) | `HarnessHook.on_tool_start` in `ze_memory/constraint_veto.py` calls `tool_interrupt_fn` | reviewed constraints | in-hook interrupt (unsafe) |
| Workflow step | `ze_automation/bootstrap.py` runs `workflow_graph.ainvoke` (`apps/ze-api/ze_api/workflow_graph.py`, reuses `capability_check` + `execute_tool`) | same as single turn; `after_capability_check_workflow` fails the step on non-EXECUTE | graph checkpoint exists (workflow thread) |
| Goal milestone | `GoalExecutor` (`goals/executor.py:769`) builds `AgentContext(gate_decision=EXECUTE)` and calls `agent.run(ctx)` directly | none: every write runs | none (no graph) |
| Companion direct call | `CompanionAgent._attempt_log_outreach` → `call_tool("log_outreach_event")` | none | none (`log_outreach_event` opts out) |

`tool_interrupt_fn` is set in `_run_with_timeout`, which the compound gather also uses. The 171 Follow-ups branch adds `tool_interrupts=False` for gather children and a `workspace_confirmed` flag to confirm goal writes after a graph-level approval. 181 deletes both.

**LangGraph resume semantics** (why in-loop interrupts are unsafe): on `Command(resume=…)` the interrupted **node re-executes from its start**; `interrupt()` returns the resume value only to the call at the same index. Everything the node did before the interrupt (LLM calls, tools) runs again. A pause is safe only when it is the first effectful thing in its node, which is how `await_subtask_confirmation` is built.

## R2. Park-and-resume design

**Decision**: parking is an exception-based unwind from `agentic_loop`, caught at three boundaries; the pause is a dedicated graph node whose first statement is `interrupt()`; resume re-enters `agent.run()` with a saved transcript on the context.

1. **Detect** (in `call_tool`, after the retry refusal): resolve `AskDecision` for the call from `ToolSpec.asks_first`, `ToolSpec.ask_check(args, ctx)` and the constraint veto (R5). If it asks and the call is not in `ctx.approved_calls`, return a `ToolCall(parked=True, …)` carrying a `ParkedWrite`; do not run hooks' `on_tool_start` side effects other than the veto evaluation.
2. **Park** (in `agentic_loop`): after dispatching every tool call of the current model response, if any `ToolCall.parked`, build `ParkedLoop(agent, messages, accumulated, iteration, parked=[…])` and raise `LoopParked(parked_loop)`. Calls in the same response that ran keep their tool messages in the transcript; parked calls have no tool message yet.
3. **Catch** at:
   - `run_delegate`: catches `LoopParked` from the specialist and returns a `ToolCall(parked=True, child=ParkedLoop, …)`; the companion's loop then parks with `ParkedLoop.child` set and `child_call_id` = the delegate call id.
   - `_run_with_timeout` (single and each gather child): catches `LoopParked` and returns a `ParkedSubtask(index, loop)` instead of an `AgentResult`. **No interrupt anywhere below the node.** `tool_interrupt_fn`, `workspace_confirmed`, `ToolConfirmationRequired` are deleted.
   - `GoalExecutor` milestone run: catches `LoopParked` and holds the milestone (R7).
4. **Pause**: `execute_tool` writes `parked_subtasks` (+ finished `subtask_results`, as 158 already does) to state; `after_execute_tool` routes to a new node `await_write_confirmation`, whose first statement is `interrupt(payload)`. The payload is the `WriteConfirmation` (request id, round, items). On resume the node writes `write_decisions` and routes back to `execute_tool`.
5. **Resume**: `execute_tool` sees `parked_subtasks` + `write_decisions`: it runs only parked subtasks, each with `ctx.resume = ParkedLoop` and `ctx.write_decisions`. `agent.run()` executes from its top (rebuilds system prompt and deps: nothing unserialisable is saved); `agentic_loop` detects `ctx.resume`, **replaces** the fresh `messages` with the saved transcript, restores `accumulated` and the iteration counter, and **before any model call**:
   - for each parked write of this loop, in order: approved → `call_tool(…, approved=True)` with the saved args (or the edited args); denied/timeout → a synthetic `ToolCall(gate="denied")` with result "The user declined; nothing was done."; append the tool message for its `call_id`;
   - if `ParkedLoop.child` is set: call `run_delegate(..., resume=child)`, whose result becomes the tool message for `child_call_id` (it may raise `LoopParked` again, which re-parks this loop with the new child).
   Then the loop continues normally and may park again (new round).
6. **approved == executed**: the approved arguments come from `ParkedWrite.args` in the checkpoint, never from a model call; `call_tool(approved=True)` is reachable only from the resume branch and only for the `call_id`s in `write_decisions`; a resumed model that emits the same call again parks again (it is a new call id).

**Alternatives rejected**:
- Return-value propagation instead of an exception: every agent's `run()` post-processing (`publish_honest_reply`, contact extraction) would run on a half-finished transcript. The exception skips it; the resumed `run()` does it once at the end.
- Saving the whole `AgentContext`: it holds callables (`token_sink`, `evaluate_delegate`, `identity_builder`, stores). Only the transcript, accumulated tool calls, iteration and parked writes are saved.
- Keeping `interrupt()` at tool level on the single path only (old option C in scope Q3): rejected by the user.

## R3. Checkpoint serialisation

`AgentState` is checkpointed by `AsyncPostgresSaver` with the serde allow-list from `checkpoint_serde_modules()`. New dataclasses (`ParkedWrite`, `ParkedLoop`, `ParkedSubtask`, `WriteConfirmation`, `WriteDecision`) live in `ze_agents/park.py` (pure dataclasses, JSON-safe fields: `str`, `dict`, `list`, `int`) and `ze_agents.park` is added to the core serde modules. `ToolCall` is already serialisable (it is in `AgentResult`). Restart test: build state → serialise with the real serde → load → resume (US2 scenario 6).

## R4. Confirmation frame and transport

Today: `send_confirmation_request` (`apps/ze-api/ze_api/api/websocket/confirmation.py`) sends `{"type": "confirm_request", id, prompt, editable, proposed, actions}` and saves a `pending_confirmations` row keyed by `request_id` (113); `handle_confirm` resumes with `{"choice", "edited_content"}`; a timeout task aborts the checkpoint; a completed turn on the thread clears stale rows (supersede). ze-web: `features/respond-to-confirmation/api/useConfirmation.ts`, consumed by `widgets/chat-workspace`.

**Decision**: hard-cut the frame to the items shape (contract: `contracts/ws-confirmation.md`): `confirm_request` gains `kind` (`write` | `budget`) and `items[]`; the reply `confirm` carries `choice` (`approve` | `deny`) and optional `edits: {item_id: text}`. `prompt/editable/proposed` at the top level are removed. **Timeout** no longer aborts the checkpoint: it resumes the graph with `{"choice": "timeout"}` so parked loops get the declined result and the "didn't" lines are produced (C2); the reply is delivered by `send_with_thread` (push when offline). Supersede keeps today's behaviour (clear rows) and additionally records `superseded` outcomes on the trace of the superseding turn.

The workspace page's REST reset (`workspace_rest.has_pending_reset`) is a user-origin action from `/workspace`, not a tool call; it is out of scope and unchanged.

## R5. Constraint veto at park time (144)

`ConstraintVetoHook.on_tool_start` today returns `None` (allow), raises `HookAbort` (veto) or calls the interrupt for `CONFIRM`. **Decision**: split the hook's matching into a pure `evaluate(tool_name, args, ctx) -> VetoOutcome(ALLOW|CONFIRM(text)|VETO(payload))` exposed as a `ConstraintCheck` and registered on the call path (the hook keeps only the VETO abort for non-park paths, or is deleted if `call_tool` calls the check directly; plan task chooses the smaller diff). `call_tool` calls it for `constraint_gate` tools before parking: VETO → refuse (today's `HookAbort` result), CONFIRM → park with `conflict=text` even when `asks_first=False`, ALLOW → normal decision. On resume an approved call does not re-check (the user saw the conflict).

## R6. Spend budget (113)

`capability_check` today composes `SpendBudgetChecker.check()` into the gate, and `bind_delegate_evaluator` composes it per delegate. **Decision**: `capability_check` is replaced by `preflight` (blocked-agent + budget). Over budget → route to `await_budget_confirmation` (first statement `interrupt({"kind": "budget", …})`); approve → `execute_tool`; deny → `record_trace` with a fixed reply. The per-delegate budget check is deleted with the delegate gate (one check per turn, before execution). Retry turns skip the budget pause (they cannot write; today's retry already overrides AWAIT_CONFIRMATION to EXECUTE).

## R7. Unattended: pre-approval and holds

- **Where pre-approval lives**: `WorkflowStep` is stored inside `workflows.steps` JSONB, so `WorkflowStep.approved_writes: list[str]` needs no migration. `Milestone` is a row in `goal_milestones` → column `approved_writes TEXT[] NOT NULL DEFAULT '{}'` (migration).
- **How the plan names them**: deterministic, no new LLM output. When a plan is created or a step edited, `planned_writes(step)` = asks-first tools in the step's agent's tool list (`agent_hint`; a step without an agent hint names none and will hold). The approval moment is the tool call that creates or edits the plan: `create_workflow`, `create_goal` and `edit_workflow_steps` get an `ask_check` that asks when the plan names any asks-first tool; their confirmation item lists "Step 2 (messenger) may: send an email, archive an email". Approving that item sets `approved_writes` for those steps. `create_workflow`/`create_goal` stay REVERSIBLE (their undo stays), but the check makes them ask in that case. A plan that names no asks-first tool is created without asking.
- **Run time**: the workflow graph runs `execute_tool` like a turn; an un-pre-approved asks-first call parks; `after_execute_tool` in the workflow graph routes to `await_write_confirmation` too; `bootstrap.py`'s runner sees `graph state.next` and, instead of finishing, creates a **held write** (`held_writes` row: request id, source `workflow`, workflow execution id, thread config, items, `expires_at = now + 24h`) and calls `ProactiveNotifier.notify()` with a new `PushKind` `write_approval_held` in class *requested*. The goal executor catches `LoopParked`, sets the milestone to a new status `held`, saves the parked loop in the held-write row (payload), and pushes the same kind.
- **Answering**: REST `POST /api/v0/held-writes/{request_id}/decision` (approve / deny / edits); the ntfy push deep-links to the notification; the notification center entry carries Approve / Deny; when the web client is connected, a `confirm_request` frame with `kind: "held"` is sent to the active connection and replayed on connect, and `handle_confirm` routes a held request id to the held-write resumer. Expiry: a `HeldWriteExpiryJob` (hourly) resumes expired holds with `timeout`.
- **Pre-approved calls**: the runner passes `ctx.pre_approved_writes = step.approved_writes`; `call_tool` treats a call whose tool is in that set as approved (outcome `pre_approved` on the trace).
- **Scheduled jobs**: no proactive job calls `call_tool` or an agent on `main` (grep: only `GoalExecutor`). The rule holds structurally: a future job that runs an agent with an asks-first tool gets `LoopParked` and must hold; an unhandled `LoopParked` escaping a job fails loudly in `ProactiveScheduler` (logged error), never runs the write.
- **Workspace unattended**: WorkspaceGate allows unattended writes and runs (161: "unattended always has the computer") and denies unattended reset. The workspace `ask_check` keeps that: unattended workspace calls never hold.

## R8. Intent hard cut: every consumer

| Consumer | Uses intent for | Replacement |
|---|---|---|
| `CapabilityGate`, `capability_overrides`, `/api/v0/capabilities`, `/capabilities` WS command, ze-web "capabilities" button, `ze_api/testing.py` `make_gate`, `ze-sdk` `Mode`/`Intent` exports | gate | deleted |
| `EmbeddingRouter._primary_intent`, `route_forced`, `_envelope`, `_single_agent_envelope` | SubTask.intent | deleted; `SubTask(agent, prompt, model)` |
| `ComplexityEstimator.classify(prompt, intent, confidence)` | `intent == "reason"` adds 2 | parameter removed; the companion bonus becomes `agent == "companion"` (same behaviour: "reason" is only declared by companion) |
| Fallback decomposer prompt (`routing/fallback.py`) | lists each agent's intents; picks a `reason` fallback agent | prompt lists agents without intents and asks a per-subtask `"changes": true|false`; fallback agent = `companion` by name (only agent with `reason` today) |
| 155 `is_mixed_gather_act` / `apply_conductor_rewrite` | gather vs act from subtask intent | `SubTask.changes: bool` set only by the decomposer; `is_mixed_gather_act` = several agents and both `changes` true and false. **Flagged to the user as a plan decision** (Q5 deleted `SubTask.intent`; 155 still needs a gather/act label) |
| `conductor_hint` entries `{agent, intent, prompt}` | display | `{agent, prompt, changes}` |
| `delegate_to_agent` `intent` argument | delegate gate | argument removed from the schema |
| `AgentContext.intent`, `gate_decision`, `evaluate_delegate` | progress keys (calendar, workflow), gate | `intent`/`gate_decision`/`evaluate_delegate` deleted; calendar/workflow use one progress key each |
| `RetrievalRequest.intent` (`fetch_context`) | carried, never read | field deleted |
| `turn.py` `_confirmation_meta` action, trace `intent` fields | display | replaced by the write items |
| `WorkflowStep.intent`, `Milestone.intent` (+ `goal_milestones.intent` column, REST payloads) | fed `SubTask.intent` in the workflow graph and goal executor | deleted (column dropped in the same migration) |
| `GateDecision` enum, `Mode` enum, `_MODE_*` tables | gate | deleted; `blocked` agents handled in `preflight` |
| `draft_response`, `await_confirmation`, `await_subtask_confirmation`, `after_capability_check`, `after_await_*`, state fields `gate_decision`, `subtask_gate_decisions`, `pending_subtask_awaits`, `approved_subtask_indexes`, `denied_subtask_indexes`, `approved_agents`, `session_overrides`, `pending_confirmation` | gate path | deleted; new fields per data-model |
| eval `judge.py` "a call marked draft…" and `is_draft` in the eval route | draft calls | "a call marked parked waits for the user's approval"; `parked` replaces `is_draft` |

`ToolCall.is_draft` and the DRAFT suppression in `call_tool` are deleted (DRAFT mode no longer exists).

## R9. Audit implementation details

- `pause_goal` ↔ `resume_goal` become REVERSIBLE with each other as `undo_tool` and an `undo_note`; `_validate_undo_tools` already checks the pairing.
- Opt-out reasons are the table's text, verbatim, in `no_ask_reason`.
- Workspace tools declare `asks_first=False`, `no_ask_reason="WorkspaceGate decides per action and origin"` and `ask_check=workspace_ask_check` (action from the tool, origin from `workspace_run_origin`). The check maps WorkspaceGate `CONFIRM` → ask, `ALLOW` → run, `DENY` → refuse (today's deny error).
- `ingest_workspace_file` opts out without a check.
- `create_workflow`, `create_goal`, `edit_workflow_steps`: `ask_check=plan_writes_check` (R7). `edit_workflow_steps` stays asks-first by the table; its check only enriches the item with the steps' planned writes.

## R10. Eval support

The eval runner (`core/ops/ze-eval/ze_eval/runner.py`) has no way to answer a confirmation today (`pending_confirmation` is only reported to the judge). **Decision**: the eval route gains `POST /api/v0/eval/confirm` (approve / deny / edits for the thread's open `request_id`), and scenario YAML gains a turn step `confirm: approve|deny`. The new scenarios use it. (Corrects the spec assumption that the harness can already answer.)

## R11. Docs touched (coverage list for [DOCS] tasks)

`README.md`, `docs/architecture.md`, `docs/adding-an-agent.md`, `docs/sdk.md`, `docs/extending-ze.md`, `docs/native-interface.md`, `docs/configuration.md`, `docs/workflows.md`, `docs/goals.md`, `docs/eval.md`, `docs/cognitive-architecture.md`, `docs/package-architecture.md`, `docs/scheduled-jobs.md`, `docs/system-one.md` (routing Choice mentions intents), `docs/deployment.md` (capabilities), diagrams `docs/diagrams/docs/turn-lifecycle.*`, `graph-node-flow.*`, `workflow-graph.*`, `root/graph-flow.*`, package READMEs `core/automation/ze-automation/README.md`, `core/cognition/ze-worldstate/README.md`, `core/engine/ze-core/README.md`, `core/contracts/ze-agents/README.md`, `packages/ze-sdk/README.md`, `AGENTS.md` (graph flow, conventions line on WRITE tools, phase row, migration table), `specs/README.md` index. Each must be checked against `git diff main...HEAD` at the end.
