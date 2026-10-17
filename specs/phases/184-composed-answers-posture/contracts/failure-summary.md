# Contract: `failure_summary(execution)` (`ze_automation/workflow/failure.py`)

Normative for FR-012 and FR-013. Pure; no I/O; no model call.

## Inputs

`WorkflowExecution` (`status`, `step_results`, `steps_snapshot`, `error`).

## Output

- `status != "failed"` → `None`.
- Let `n = len(steps_snapshot)` if non-empty, else `max(step_index) + 1` over `step_results`, else unknown.
- If any `StepResult.success is False`: take the **last** failed result `r`.
  - `"Step {r.step_index + 1} of {n}, “{task}”, failed: {reason}{attempts}."` (drop " of {n}" when unknown).
  - `task` = `r.task` collapsed to one line, cut at 60 characters with "…".
  - `attempts` = `" after {r.attempt_count} attempts"` when `attempt_count > 1`, else empty.
- Else if `error` is set and `step_results` is empty: `"The run stopped before its first step: {reason}."`
- Else if `error` is set (steps ran and all succeeded, then the execution failed: cancellation between steps, spend-budget pause, deletion while held, a declined or expired write): `"The run stopped after step {k} of {n}: {reason}."` with `k = max(step_index) + 1` over the successful results (drop " of {n}" when unknown).
- Else: `"The run failed without saying why."`

## `reason` (first match wins, case-insensitive, over the failed step's `error` or the execution's `error`)

| Pattern | Reason |
|---|---|
| `timeout`, `timed out`, `TimeoutError` | `it ran out of time` |
| `deleted while held` | `the workflow was deleted while it waited for your OK` |
| `user denied`, `user declined`, `denied by the user`, `declined by the user`, `refused by the user`, `write denied`, `write declined`, `declined the write` | `you declined the write it needed` |
| `approval expired`, `hold expired`, `hold has expired`, `held write expired` | `your OK did not come in time` |
| `spend budget`, `budget exceeded`, `budget pause` | `the spend budget paused it` |
| `cancel` | `it was cancelled` |
| `no results`, or `r.no_results` | `it found nothing to work with` |
| anything else | `it hit an error` |

The raw `error` string never appears in the output (fixtures include each execution-level reason after successful steps; test: for every fixture, `error not in failure_summary(ex)` and no substring longer than 12 characters of `error` appears).

## Consumers

- `ze_automation/rest.py` execution dicts → `WorkflowExecutionResponse.failure_summary`.
- `ze_automation/agents/workflow/tools.py` `_serialize_execution` → key `failure_summary`.
- `ze_automation/bootstrap.py` `_workflow_failure_handler` push body: `failure_summary(execution)` when an execution is found, else `"The run failed before it started."`.
