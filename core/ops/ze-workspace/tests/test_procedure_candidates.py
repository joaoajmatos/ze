from __future__ import annotations

from uuid import uuid4

from ze_workspace.procedure_candidates import (
    candidate_from_workspace_run,
    workspace_run_is_approved,
)
from ze_workspace.types import (
    WorkspaceMode,
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
)


def _run(**overrides) -> WorkspaceRun:
    data = dict(
        command="ls notes",
        origin=WorkspaceRunOrigin.USER,
        status=WorkspaceRunStatus.SUCCEEDED,
        id=uuid4(),
    )
    data.update(overrides)
    return WorkspaceRun(**data)


def test_user_success_is_approved() -> None:
    run = _run()
    assert workspace_run_is_approved(run, WorkspaceMode.ASK) is True
    candidate = candidate_from_workspace_run(run, mode=WorkspaceMode.ASK)
    assert candidate.workspace_run_approved is True
    assert candidate.source_kind.value == "workspace_run"


def test_unapproved_failed_run_is_rejected() -> None:
    run = _run(status=WorkspaceRunStatus.FAILED)
    candidate = candidate_from_workspace_run(run, mode=WorkspaceMode.AUTO)
    assert candidate.workspace_run_approved is False
