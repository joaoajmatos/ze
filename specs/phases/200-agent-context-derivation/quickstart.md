# Quickstart: validating phase 200

Everything runs offline: no database, no OpenRouter, no Docker. Run from the repo root of the floor checkout.

## 1. The declaration tests (SC-002, SC-003)

```bash
make test-agents   # tests/test_derive_table.py, tests/test_lifetime.py
make test-core     # tests/orchestration/test_state_lifetimes.py, tests/conversation/test_make_graph_input.py
make test-personal # tests/graph/test_workflow.py (WorkflowAgentState fields are Run)
```

Expected:
- `test_derive_table` finds a rule for every `AgentContext` field for each of the four kinds, and every `Reset` carries a reason.
- `test_state_lifetimes` finds a lifetime for every `AgentState` and `WorkflowAgentState` key.
- `make_graph_input` sets every `Turn` key to its reset value and every `Input` key from the raw input, and leaves out every `Thread` and `Run` key.

Negative checks (written as tests, listed here so a reviewer can try them by hand):
- Add `foo: int = 0` to `AgentContext`. `test_derive_table` fails and names `foo`.
- Add `bar: int` with no marker to a test `TypedDict` extension. `build_state_type([plugin])` raises `UndeclaredLifetimeError` naming `bar`.

## 2. The turn's facts reach every run (US1, SC-005)

```bash
make test-core       # tests/orchestration/nodes/test_execution_derivation.py
make test-agents     # tests/test_delegate.py
make test-automation # tests/goal_engine/test_executor.py
```

Expected: with `timezone="Europe/Lisbon"` and `extensions={"user_message_id": "m1"}` on the turn context, all of these see Lisbon time in their system prompt and can read `user_message_id`:
- the single-specialist context;
- each compound subtask context;
- a delegate context (whose `extensions` also carries `_delegate_depth=1`).

A goal milestone sees the executor's timezone. A delegate context has no `token_sink`, prompt notes, skills, procedure state or conductor deadline.

## 3. One outcome, no copy-back (US2)

```bash
make test-core   # tests/orchestration/test_conductor_merge.py, test_write_confirmation_compound.py, test_procedure_activation.py
```

Expected:
- A single turn in which the companion delegates twice ends with `conductor_delegate_total == 2` in state, two `done` ledger entries, and the same in the trace.
- A delegate that parks and resumes ends with total 1 and one ledger entry (`awaiting_confirmation` → `done`).
- In a compound turn with two subtasks, the ledgers are concatenated in subtask order and the counts summed. When the turn cap is reached, the next delegate is refused, whichever subtask makes it.
- A subtask that invoked a procedure before a pause still completes that invocation after resume.
- `rg "conductor_delegate_total = |_sync_procedure_invocation|getattr\(ctx, \"conductor" core` finds nothing.

## 4. Workflow steps start clean (US3 scenario 4)

```bash
make test-personal   # tests/graph/test_workflow.py
make test            # apps/ze-api/tests/test_workflow_turn_reset.py, test_workflow_hold.py
```

Expected:
- Step 2 starts with empty `judgments`, `components`, `conductor_ledgers` and `tier`.
- `workflow_steps`, `workflow_step_results` and `visit_counts` keep their values.
- `load_workflow_step` contains no reset keys.

## 5. Whole suite and grep gates

```bash
make test-py
make lint
rg -n "AgentContext\(" --glob '*.py' core plugins apps packages integrations | rg -v "/tests/"
```

Expected:
- `test-py` is green.
- The grep lists only `ze_core/orchestration/nodes/context.py` (the turn context) and `ze_agents/derive.py` (SC-001). `eval/calibration/complexity.py` builds a synthetic turn context for calibration and is outside the source packages.
