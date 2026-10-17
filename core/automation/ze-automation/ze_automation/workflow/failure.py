from __future__ import annotations

from ze_automation.workflow.types import StepResult, WorkflowExecution

_TASK_MAX = 60

_REASONS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("timeout", "timed out"), "it ran out of time"),
    (
        ("deleted while held",),
        "the workflow was deleted while it waited for your OK",
    ),
    (
        (
            "user denied",
            "user declined",
            "denied by the user",
            "declined by the user",
            "refused by the user",
            "write denied",
            "write declined",
            "declined the write",
        ),
        "you declined the write it needed",
    ),
    (
        ("approval expired", "hold expired", "hold has expired", "held write expired"),
        "your OK did not come in time",
    ),
    (("spend budget", "budget exceeded", "budget pause"), "the spend budget paused it"),
    (("cancel",), "it was cancelled"),
    (("no results",), "it found nothing to work with"),
)
_NO_RESULTS_REASON = "it found nothing to work with"
_GENERIC_REASON = "it hit an error"


def _reason(error: str | None, *, no_results: bool = False) -> str:
    lowered = (error or "").lower()
    for needles, reason in _REASONS:
        if reason == _NO_RESULTS_REASON and no_results:
            return reason
        if any(needle in lowered for needle in needles):
            return reason
    return _GENERIC_REASON


def _one_line(task: str) -> str:
    line = " ".join(task.split())
    return line if len(line) <= _TASK_MAX else line[: _TASK_MAX - 1].rstrip() + "…"


def _step_count(execution: WorkflowExecution) -> int | None:
    if execution.steps_snapshot:
        return len(execution.steps_snapshot)
    if execution.step_results:
        return max(r.step_index for r in execution.step_results) + 1
    return None


def _of(count: int | None) -> str:
    return f" of {count}" if count is not None else ""


def failure_summary(execution: WorkflowExecution) -> str | None:
    """One plain line saying why a run failed. Never contains the raw error text."""
    if execution.status != "failed":
        return None
    count = _step_count(execution)
    failed: list[StepResult] = [r for r in execution.step_results if not r.success]
    if failed:
        last = failed[-1]
        attempts = (
            f" after {last.attempt_count} attempts" if last.attempt_count > 1 else ""
        )
        reason = _reason(last.error or execution.error, no_results=last.no_results)
        return (
            f"Step {last.step_index + 1}{_of(count)}, “{_one_line(last.task)}”, "
            f"failed: {reason}{attempts}."
        )
    if execution.error and not execution.step_results:
        return f"The run stopped before its first step: {_reason(execution.error)}."
    if execution.error:
        done = max(r.step_index for r in execution.step_results) + 1
        return f"The run stopped after step {done}{_of(count)}: {_reason(execution.error)}."
    return "The run failed without saying why."
