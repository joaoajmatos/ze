from __future__ import annotations

from ze_workspace.types import (
    WorkspaceAction,
    WorkspaceGateDecision,
    WorkspaceRunOrigin,
)

_READISH = {
    WorkspaceAction.LIST,
    WorkspaceAction.READ,
    WorkspaceAction.PLACE,
    WorkspaceAction.RETRIEVE,
}

_WRITEISH = {
    WorkspaceAction.WRITE,
    WorkspaceAction.DELETE,
    WorkspaceAction.INGEST,
}

_RUNISH = {
    WorkspaceAction.RUN,
    WorkspaceAction.RUN_SCRIPT,
}


class WorkspaceGate:
    """action × origin → allow | confirm | deny."""

    def decide(
        self,
        *,
        action: WorkspaceAction,
        origin: WorkspaceRunOrigin,
    ) -> WorkspaceGateDecision:
        if action is WorkspaceAction.RESET:
            if origin is WorkspaceRunOrigin.UNATTENDED:
                return WorkspaceGateDecision.DENY
            return WorkspaceGateDecision.CONFIRM

        if origin is WorkspaceRunOrigin.USER:
            if action in _READISH or action in _WRITEISH:
                return WorkspaceGateDecision.ALLOW
            return WorkspaceGateDecision.DENY

        if origin is WorkspaceRunOrigin.UNATTENDED:
            if action in _READISH or action in _WRITEISH or action in _RUNISH:
                return WorkspaceGateDecision.ALLOW
            return WorkspaceGateDecision.DENY

        if action in _READISH:
            return WorkspaceGateDecision.ALLOW
        if action in _WRITEISH or action in _RUNISH:
            return WorkspaceGateDecision.CONFIRM
        return WorkspaceGateDecision.DENY

    def decide_named(
        self,
        *,
        action: str,
        origin: str,
    ) -> WorkspaceGateDecision:
        return self.decide(
            action=WorkspaceAction(action),
            origin=WorkspaceRunOrigin(origin),
        )
