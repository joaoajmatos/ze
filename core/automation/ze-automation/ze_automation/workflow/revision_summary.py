from __future__ import annotations

from ze_automation.workflow.types import WorkflowStep

_COMPARED_FIELDS = (
    "task",
    "agent_hint",
    "verify",
    "branches",
    "default_next",
    "on_failure",
    "planned_writes",
    "approved_writes",
)


def _branches_value(step: WorkflowStep) -> list[tuple[str, str]]:
    return [(b.condition, b.to) for b in step.branches]


def _field_value(step: WorkflowStep, field_name: str) -> object:
    if field_name == "branches":
        return _branches_value(step)
    return getattr(step, field_name)


def build_change_summary(
    before: list[WorkflowStep], after: list[WorkflowStep], change_type: str
) -> str:
    if change_type == "created":
        return f"Workflow created with {len(after)} step(s)"

    before_by_id = {s.id: s for s in before}
    after_by_id = {s.id: s for s in after}

    clauses: list[str] = []

    for step_id, step in after_by_id.items():
        if step_id not in before_by_id:
            clauses.append(f"Step {step_id} added")

    for step_id in before_by_id:
        if step_id not in after_by_id:
            clauses.append(f"Step {step_id} removed")

    for step_id, after_step in after_by_id.items():
        before_step = before_by_id.get(step_id)
        if before_step is None:
            continue
        for field_name in _COMPARED_FIELDS:
            before_value = _field_value(before_step, field_name)
            after_value = _field_value(after_step, field_name)
            if before_value != after_value:
                clauses.append(
                    f"Step {step_id}: {field_name} {before_value} → {after_value}"
                )

    return "; ".join(clauses)


_DEFINITION_FIELDS = tuple(f for f in _COMPARED_FIELDS if f != "approved_writes")


def changed_step_ids(before: list[WorkflowStep], after: list[WorkflowStep]) -> set[str]:
    """Ids of steps in `after` that are new or differ from `before` (not counting grants)."""
    before_by_id = {s.id: s for s in before}
    changed: set[str] = set()
    for step in after:
        prior = before_by_id.get(step.id)
        if prior is None or any(
            _field_value(prior, f) != _field_value(step, f) for f in _DEFINITION_FIELDS
        ):
            changed.add(step.id)
    return changed
