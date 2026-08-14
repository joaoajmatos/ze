from __future__ import annotations

from ze_agents.errors import ZeError


class WorkspaceError(ZeError):
    """Base for workspace package errors."""


class WorkspaceUnavailableError(WorkspaceError):
    """Sidecar health check failed or the control API could not be reached."""


class WorkspaceBusyError(WorkspaceError):
    """A run is already in progress and the lock wait expired."""


class WorkspaceFullError(WorkspaceError):
    """A write would exceed the storage ceiling; the tree is unchanged."""


class WorkspacePathError(WorkspaceError):
    """Path is outside the workspace, absolute, or otherwise illegal."""


class WorkspaceNotFoundError(WorkspaceError):
    """Requested file or run does not exist."""
