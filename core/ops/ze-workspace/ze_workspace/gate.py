from __future__ import annotations

from ze_workspace.types import (
    WorkspaceAction,
    WorkspaceGateDecision,
    WorkspaceMode,
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
    """mode × action × origin → allow | confirm | plan | deny."""

    def decide(
        self,
        *,
        mode: WorkspaceMode,
        action: WorkspaceAction,
        origin: WorkspaceRunOrigin,
    ) -> WorkspaceGateDecision:
        if action is WorkspaceAction.RESET:
            return WorkspaceGateDecision.CONFIRM

        if origin is WorkspaceRunOrigin.USER:
            if action in _READISH or action is WorkspaceAction.DELETE:
                return WorkspaceGateDecision.ALLOW
            if action in _WRITEISH:
                return WorkspaceGateDecision.ALLOW
            if action in _RUNISH:
                return self._conversation_decide(mode, action)
            return WorkspaceGateDecision.DENY

        if origin is WorkspaceRunOrigin.UNATTENDED:
            return self._unattended_decide(mode, action)

        return self._conversation_decide(mode, action)

    def decide_named(
        self,
        *,
        mode: WorkspaceMode | str,
        action: str,
        origin: str,
    ) -> WorkspaceGateDecision:
        mode_e = mode if isinstance(mode, WorkspaceMode) else WorkspaceMode(mode)
        return self.decide(
            mode=mode_e,
            action=WorkspaceAction(action),
            origin=WorkspaceRunOrigin(origin),
        )

    def _conversation_decide(
        self, mode: WorkspaceMode, action: WorkspaceAction
    ) -> WorkspaceGateDecision:
        if mode is WorkspaceMode.OFF:
            return WorkspaceGateDecision.DENY
        if action in _READISH:
            return WorkspaceGateDecision.ALLOW
        if mode is WorkspaceMode.PLAN:
            if action in _WRITEISH or action in _RUNISH:
                return WorkspaceGateDecision.PLAN
            return WorkspaceGateDecision.ALLOW
        if mode is WorkspaceMode.ASK:
            if action in _WRITEISH or action in _RUNISH:
                return WorkspaceGateDecision.CONFIRM
            return WorkspaceGateDecision.ALLOW
        if mode is WorkspaceMode.AUTO_EDIT:
            if action in _WRITEISH:
                return WorkspaceGateDecision.ALLOW
            if action in _RUNISH:
                return WorkspaceGateDecision.CONFIRM
            return WorkspaceGateDecision.ALLOW
        # AUTO
        if action in _WRITEISH or action in _RUNISH or action in _READISH:
            return WorkspaceGateDecision.ALLOW
        return WorkspaceGateDecision.DENY

    def _unattended_decide(
        self, mode: WorkspaceMode, action: WorkspaceAction
    ) -> WorkspaceGateDecision:
        if action in _RUNISH:
            if mode is WorkspaceMode.AUTO:
                return WorkspaceGateDecision.ALLOW
            return WorkspaceGateDecision.DENY
        if action in {WorkspaceAction.WRITE, WorkspaceAction.DELETE}:
            if mode in {WorkspaceMode.AUTO_EDIT, WorkspaceMode.AUTO}:
                return WorkspaceGateDecision.ALLOW
            return WorkspaceGateDecision.DENY
        if action in _READISH:
            if mode is WorkspaceMode.OFF:
                return WorkspaceGateDecision.DENY
            return WorkspaceGateDecision.ALLOW
        return WorkspaceGateDecision.DENY
