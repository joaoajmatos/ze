from __future__ import annotations

from ze_workspace.gate import WorkspaceGate
from ze_workspace.types import (
    WorkspaceAction,
    WorkspaceGateDecision,
    WorkspaceMode,
    WorkspaceRunOrigin,
)

gate = WorkspaceGate()


def _d(mode: WorkspaceMode, action: WorkspaceAction, origin: WorkspaceRunOrigin):
    return gate.decide(mode=mode, action=action, origin=origin)


def test_conversation_off_denies_list():
    assert (
        _d(WorkspaceMode.OFF, WorkspaceAction.LIST, WorkspaceRunOrigin.CONVERSATION)
        is WorkspaceGateDecision.DENY
    )


def test_user_rest_list_allows_in_off():
    assert (
        _d(WorkspaceMode.OFF, WorkspaceAction.LIST, WorkspaceRunOrigin.USER)
        is WorkspaceGateDecision.ALLOW
    )


def test_user_place_read_retrieve_allow_in_off():
    for action in (
        WorkspaceAction.PLACE,
        WorkspaceAction.READ,
        WorkspaceAction.RETRIEVE,
    ):
        assert (
            _d(WorkspaceMode.OFF, action, WorkspaceRunOrigin.USER)
            is WorkspaceGateDecision.ALLOW
        )


def test_unattended_run_only_auto():
    assert (
        _d(WorkspaceMode.ASK, WorkspaceAction.RUN, WorkspaceRunOrigin.UNATTENDED)
        is WorkspaceGateDecision.DENY
    )
    assert (
        _d(WorkspaceMode.AUTO_EDIT, WorkspaceAction.RUN, WorkspaceRunOrigin.UNATTENDED)
        is WorkspaceGateDecision.DENY
    )
    assert (
        _d(WorkspaceMode.AUTO, WorkspaceAction.RUN, WorkspaceRunOrigin.UNATTENDED)
        is WorkspaceGateDecision.ALLOW
    )


def test_unattended_write_auto_edit_or_auto():
    assert (
        _d(WorkspaceMode.ASK, WorkspaceAction.WRITE, WorkspaceRunOrigin.UNATTENDED)
        is WorkspaceGateDecision.DENY
    )
    assert (
        _d(
            WorkspaceMode.AUTO_EDIT,
            WorkspaceAction.WRITE,
            WorkspaceRunOrigin.UNATTENDED,
        )
        is WorkspaceGateDecision.ALLOW
    )
    assert (
        _d(WorkspaceMode.AUTO, WorkspaceAction.WRITE, WorkspaceRunOrigin.UNATTENDED)
        is WorkspaceGateDecision.ALLOW
    )


def test_reset_always_confirm():
    for mode in WorkspaceMode:
        for origin in WorkspaceRunOrigin:
            assert (
                _d(mode, WorkspaceAction.RESET, origin)
                is WorkspaceGateDecision.CONFIRM
            )


def test_ask_confirms_write_and_run():
    assert (
        _d(WorkspaceMode.ASK, WorkspaceAction.WRITE, WorkspaceRunOrigin.CONVERSATION)
        is WorkspaceGateDecision.CONFIRM
    )
    assert (
        _d(WorkspaceMode.ASK, WorkspaceAction.RUN, WorkspaceRunOrigin.CONVERSATION)
        is WorkspaceGateDecision.CONFIRM
    )


def test_auto_edit_allows_write_confirms_run():
    assert (
        _d(
            WorkspaceMode.AUTO_EDIT,
            WorkspaceAction.WRITE,
            WorkspaceRunOrigin.CONVERSATION,
        )
        is WorkspaceGateDecision.ALLOW
    )
    assert (
        _d(
            WorkspaceMode.AUTO_EDIT,
            WorkspaceAction.RUN,
            WorkspaceRunOrigin.CONVERSATION,
        )
        is WorkspaceGateDecision.CONFIRM
    )


def test_plan_dry_run():
    assert (
        _d(WorkspaceMode.PLAN, WorkspaceAction.WRITE, WorkspaceRunOrigin.CONVERSATION)
        is WorkspaceGateDecision.PLAN
    )
    assert (
        _d(WorkspaceMode.PLAN, WorkspaceAction.RUN, WorkspaceRunOrigin.CONVERSATION)
        is WorkspaceGateDecision.PLAN
    )
