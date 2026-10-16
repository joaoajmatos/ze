"""WorkspaceGate decisions as pre-call checks (Phase 181, Q9)."""

from __future__ import annotations

import pytest

from ze_agents.interrupt import workspace_run_origin
from ze_workspace.gate import WorkspaceGate
from ze_workspace.tools import configure, workspace_ask_check
from ze_workspace.types import WorkspaceAction

_ACTIONS = {
    "write": WorkspaceAction.WRITE,
    "delete": WorkspaceAction.DELETE,
    "run": WorkspaceAction.RUN,
    "script": WorkspaceAction.RUN_SCRIPT,
    "reset": WorkspaceAction.RESET,
}


@pytest.fixture(autouse=True)
def _wired():
    configure(client=None, gate=WorkspaceGate(), store=None)


def _kind(origin: str, action: str, args: dict | None = None):
    token = workspace_run_origin.set(origin)
    try:
        return workspace_ask_check(_ACTIONS[action])(args or {"command": "ls"}, None)
    finally:
        workspace_run_origin.reset(token)


@pytest.mark.parametrize("action", ["write", "delete"])
def test_user_writes_run(action) -> None:
    assert _kind("user", action).kind == "run"


@pytest.mark.parametrize("action", ["write", "delete", "run", "script"])
def test_agent_writes_and_runs_ask(action) -> None:
    decision = _kind("conversation", action)
    assert decision.kind == "ask" and decision.reason


@pytest.mark.parametrize("action", ["write", "delete", "run", "script"])
def test_unattended_writes_and_runs_run(action) -> None:
    assert _kind("unattended", action).kind == "run"


def test_reset_asks_unless_unattended() -> None:
    assert _kind("conversation", "reset").kind == "ask"
    assert _kind("user", "reset").kind == "ask"
    decision = _kind("unattended", "reset")
    assert decision.kind == "refuse"
    assert decision.message == "Resetting the workspace is not allowed."


def test_user_runs_are_refused_with_todays_message() -> None:
    decision = _kind("user", "run")
    assert decision.kind == "refuse"
    assert decision.message == "Running commands in the workspace is not allowed."


def test_ask_reason_names_the_target() -> None:
    assert "rm -rf /" in _kind("conversation", "run", {"command": "rm -rf /"}).reason
    assert "a.txt" in _kind("conversation", "delete", {"path": "a.txt"}).reason
