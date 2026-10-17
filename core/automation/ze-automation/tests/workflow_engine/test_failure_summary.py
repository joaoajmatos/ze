from __future__ import annotations

from uuid import uuid4

import pytest
from ze_automation.workflow.failure import failure_summary
from ze_automation.workflow.types import StepResult, WorkflowExecution, WorkflowStep


def _step(index: int, *, success=True, error=None, task=None, **kw) -> StepResult:
    return StepResult(
        step_index=index,
        task=task or f"Task {index + 1}",
        output="",
        success=success,
        error=error,
        duration_ms=10,
        **kw,
    )


def _execution(
    results=(), *, snapshot=4, status="failed", error=None
) -> WorkflowExecution:
    return WorkflowExecution(
        id=uuid4(),
        workflow_id=uuid4(),
        status=status,
        step_results=list(results),
        steps_snapshot=[WorkflowStep(task=f"Step {i}") for i in range(snapshot)],
        error=error,
    )


def test_completed_execution_has_no_summary():
    assert failure_summary(_execution(status="completed")) is None
    assert failure_summary(_execution(status="running")) is None


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("TimeoutError: step took too long", "it ran out of time"),
        ("operation timed out", "it ran out of time"),
        (
            "workflow deleted while held",
            "the workflow was deleted while it waited for your OK",
        ),
        ("User denied the write", "you declined the write it needed"),
        ("write declined", "you declined the write it needed"),
        ("refused by the user", "you declined the write it needed"),
        ("approval expired", "your OK did not come in time"),
        ("spend budget reached", "the spend budget paused it"),
        ("Cancelled by user", "it was cancelled"),
        ("no results for query", "it found nothing to work with"),
        ("KeyError: 'rows'", "it hit an error"),
    ],
)
def test_failed_step_reason_table(raw, reason):
    ex = _execution(
        [_step(0), _step(1, success=False, error=raw, task="Check the inbox")]
    )
    assert failure_summary(ex) == (f"Step 2 of 4, “Check the inbox”, failed: {reason}.")


def test_reason_priority_is_first_match():
    ex = _execution([_step(0, success=False, error="timeout while waiting for cancel")])
    assert "it ran out of time" in failure_summary(ex)


def test_no_results_flag_is_a_reason():
    ex = _execution([_step(0, success=False, error=None, no_results=True)])
    assert (
        failure_summary(ex)
        == "Step 1 of 4, “Task 1”, failed: it found nothing to work with."
    )


def test_attempts_are_named_when_more_than_one():
    ex = _execution([_step(1, success=False, error="timed out", attempt_count=3)])
    assert failure_summary(ex) == (
        "Step 2 of 4, “Task 2”, failed: it ran out of time after 3 attempts."
    )


def test_last_failed_result_is_used():
    ex = _execution(
        [
            _step(0, success=False, error="boom", task="First"),
            _step(2, success=False, error="timed out", task="Third"),
        ]
    )
    assert failure_summary(ex).startswith("Step 3 of 4, “Third”")


def test_unknown_step_count_drops_of_n():
    ex = _execution([_step(1, success=False, error="timed out")], snapshot=0)
    assert failure_summary(ex) == "Step 2 of 2, “Task 2”, failed: it ran out of time."
    ex = _execution([_step(1, success=False, error="x")], snapshot=0)
    ex.step_results = [_step(1, success=False, error="x")]
    # n comes from the highest step index when there is no snapshot
    assert "of 2" in failure_summary(ex)


def test_unknown_count_when_no_snapshot_and_no_results_for_execution_error():
    ex = _execution(snapshot=0, error="Cancelled")
    assert (
        failure_summary(ex)
        == "The run stopped before its first step: it was cancelled."
    )


def test_task_is_one_line_and_cut_at_sixty():
    long_task = "Read\nthe   whole inbox and " + "x" * 80
    ex = _execution([_step(0, success=False, error="boom", task=long_task)])
    summary = failure_summary(ex)
    quoted = summary.split("“", 1)[1].split("”", 1)[0]
    assert "\n" not in quoted
    assert len(quoted) <= 61 and quoted.endswith("…")


def test_stopped_before_first_step():
    ex = _execution(error="spend budget exceeded")
    assert (
        failure_summary(ex)
        == "The run stopped before its first step: the spend budget paused it."
    )


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("Cancelled between steps", "it was cancelled"),
        ("spend budget pause", "the spend budget paused it"),
        (
            "workflow deleted while held",
            "the workflow was deleted while it waited for your OK",
        ),
        ("write denied", "you declined the write it needed"),
        ("hold expired", "your OK did not come in time"),
        ("???", "it hit an error"),
    ],
)
def test_execution_level_reasons_after_successful_steps(raw, reason):
    ex = _execution([_step(0), _step(1)], error=raw)
    assert failure_summary(ex) == f"The run stopped after step 2 of 4: {reason}."


def test_execution_level_reason_without_known_count():
    ex = _execution([_step(0)], snapshot=0, error="Cancelled")
    assert failure_summary(ex) == "The run stopped after step 1 of 1: it was cancelled."


def test_failure_without_a_reason():
    assert (
        failure_summary(_execution([_step(0)])) == "The run failed without saying why."
    )


def _windows(text: str, size: int):
    return {text[i : i + size] for i in range(max(0, len(text) - size + 1))}


def test_raw_error_text_never_appears():
    raws = [
        "TimeoutError: step took too long after 30s of waiting",
        "Traceback (most recent call last): File x.py line 3 KeyError rows",
        "Cancelled between steps because of a user request",
        "ValueError: invalid literal for int() with base 10",
    ]
    for raw in raws:
        for ex in (
            _execution([_step(0, success=False, error=raw)]),
            _execution([_step(0)], error=raw),
            _execution(error=raw),
        ):
            summary = failure_summary(ex)
            assert raw not in summary
            assert not (_windows(raw, 13) & _windows(summary, 13))
