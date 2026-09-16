from __future__ import annotations

from uuid import UUID

from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.types import ProcedureVersion, VersionStatus


async def project_procedure_history(
    service: ProcedureAdmissionService, procedure_id: UUID
) -> dict:
    history = await service.lifecycle_history(procedure_id)
    versions: list[ProcedureVersion] = history["versions"]
    return {
        **history,
        "active": [v for v in versions if v.status is VersionStatus.ACTIVE],
        "inactive": [v for v in versions if v.status is not VersionStatus.ACTIVE],
    }
