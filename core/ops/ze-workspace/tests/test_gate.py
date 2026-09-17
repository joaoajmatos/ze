from __future__ import annotations

import inspect

from ze_workspace import rest as workspace_rest
from ze_workspace.gate import WorkspaceGate
from ze_workspace.types import (
    WorkspaceAction,
    WorkspaceGateDecision,
    WorkspaceRunOrigin,
)

gate = WorkspaceGate()


def _d(action: WorkspaceAction, origin: WorkspaceRunOrigin):
    return gate.decide(action=action, origin=origin)


def test_conversation_reads_allow():
    assert (
        _d(WorkspaceAction.LIST, WorkspaceRunOrigin.CONVERSATION)
        is WorkspaceGateDecision.ALLOW
    )
    assert (
        _d(WorkspaceAction.READ, WorkspaceRunOrigin.CONVERSATION)
        is WorkspaceGateDecision.ALLOW
    )


def test_conversation_writes_and_runs_confirm():
    for action in (
        WorkspaceAction.WRITE,
        WorkspaceAction.DELETE,
        WorkspaceAction.INGEST,
        WorkspaceAction.RUN,
        WorkspaceAction.RUN_SCRIPT,
        WorkspaceAction.RESET,
    ):
        assert (
            _d(action, WorkspaceRunOrigin.CONVERSATION)
            is WorkspaceGateDecision.CONFIRM
        )


def test_unattended_allows_write_and_run_denies_reset():
    assert (
        _d(WorkspaceAction.RUN, WorkspaceRunOrigin.UNATTENDED)
        is WorkspaceGateDecision.ALLOW
    )
    assert (
        _d(WorkspaceAction.WRITE, WorkspaceRunOrigin.UNATTENDED)
        is WorkspaceGateDecision.ALLOW
    )
    assert (
        _d(WorkspaceAction.RESET, WorkspaceRunOrigin.UNATTENDED)
        is WorkspaceGateDecision.DENY
    )


def test_user_rest_list_and_place_allow_run_deny():
    assert _d(WorkspaceAction.LIST, WorkspaceRunOrigin.USER) is WorkspaceGateDecision.ALLOW
    assert _d(WorkspaceAction.PLACE, WorkspaceRunOrigin.USER) is WorkspaceGateDecision.ALLOW
    assert _d(WorkspaceAction.RUN, WorkspaceRunOrigin.USER) is WorkspaceGateDecision.DENY
    assert (
        _d(WorkspaceAction.RESET, WorkspaceRunOrigin.USER)
        is WorkspaceGateDecision.CONFIRM
    )


def test_workspace_action_has_no_cancel_member():
    assert not hasattr(WorkspaceAction, "CANCEL")


def test_cancel_run_never_calls_workspace_gate():
    source = inspect.getsource(workspace_rest.cancel_run)
    body = source.split('"""', 2)[-1]
    assert "WorkspaceGate" not in body
    assert "gate" not in body
    assert ".decide(" not in body
