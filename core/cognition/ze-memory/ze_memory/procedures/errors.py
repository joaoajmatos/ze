from __future__ import annotations

from ze_memory.errors import MemoryError


class ProcedureLifecycleError(MemoryError):
    pass


class IncompleteProcedureCandidateError(ProcedureLifecycleError):
    pass


class InvalidProcedureEvidenceError(ProcedureLifecycleError):
    pass


class UnapprovedWorkspaceRunError(ProcedureLifecycleError):
    pass


class InvalidProcedureTransitionError(ProcedureLifecycleError):
    pass


class MissingActionRecordError(ProcedureLifecycleError):
    pass


class UnavailableRollbackTargetError(ProcedureLifecycleError):
    pass


class IneligibleProcedureError(ProcedureLifecycleError):
    pass


class BlockedProcedureError(ProcedureLifecycleError):
    pass


class StaleProcedureInvocationError(ProcedureLifecycleError):
    pass
