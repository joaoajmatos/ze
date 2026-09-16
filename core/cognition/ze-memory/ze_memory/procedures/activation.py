from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.errors import (
    BlockedProcedureError,
    IneligibleProcedureError,
    StaleProcedureInvocationError,
)
from ze_memory.procedures.store import ProcedureStore
from ze_memory.procedures.types import (
    CapabilityDecision,
    IdentityStatus,
    InvocationState,
    MatchState,
    ProcedureActionLink,
    ProcedureActionOutcome,
    ProcedureInvocation,
    ProcedureInvocationOrigin,
    ProcedureMatch,
    ProcedureOutcome,
    ProcedureOutcomeFeedback,
    VersionStatus,
)

UTC = timezone.utc


class ProcedureActivator:
    def __init__(self, store: ProcedureStore) -> None:
        self._store = store

    async def invoke(
        self,
        match: ProcedureMatch,
        *,
        origin: ProcedureInvocationOrigin,
        caller: str,
        task_context_ref: str | None = None,
    ) -> ProcedureInvocation:
        if match.state is not MatchState.READY:
            raise BlockedProcedureError("procedure is not ready to invoke")
        version = await self._store.get_version(match.version_id)
        if version is None or version.status is not VersionStatus.ACTIVE:
            raise IneligibleProcedureError("procedure version is not eligible")
        identity = await self._store.get_identity(match.procedure_id)
        if identity is None or identity.status is not IdentityStatus.ACTIVE:
            raise IneligibleProcedureError("procedure is disabled")
        if identity.active_version_id != match.version_id:
            raise IneligibleProcedureError("procedure version is stale")
        return await self._store.save_invocation(
            ProcedureInvocation(
                procedure_id=match.procedure_id,
                version_id=match.version_id,
                origin=origin,
                caller=caller,
                task_context_ref=task_context_ref,
            )
        )

    async def record_action(
        self,
        invocation_id: UUID,
        *,
        step_ref: str,
        action_trace_ref: str | None,
        capability_decision: CapabilityDecision,
        outcome: ProcedureActionOutcome,
    ) -> ProcedureActionLink:
        invocation = await self._store.get_invocation(invocation_id)
        if invocation is None or invocation.id is None:
            raise StaleProcedureInvocationError("invocation not found")
        if invocation.state is not InvocationState.STARTED:
            raise StaleProcedureInvocationError("invocation already finished")
        return await self._store.save_action_link(
            ProcedureActionLink(
                invocation_id=invocation.id,
                procedure_id=invocation.procedure_id,
                version_id=invocation.version_id,
                step_ref=step_ref,
                capability_decision=capability_decision,
                outcome=outcome,
                action_trace_ref=action_trace_ref,
            )
        )

    async def complete(
        self,
        invocation_id: UUID,
        *,
        outcome: ProcedureOutcome,
        summary: str,
    ) -> ProcedureOutcomeFeedback:
        existing = await self._store.get_activation_feedback(invocation_id)
        if existing is not None:
            return existing
        invocation = await self._store.get_invocation(invocation_id)
        if invocation is None or invocation.id is None:
            raise StaleProcedureInvocationError("invocation not found")
        links = await self._store.list_action_links(invocation.id)
        feedback = await self._store.save_activation_feedback(
            ProcedureOutcomeFeedback(
                invocation_id=invocation.id,
                procedure_id=invocation.procedure_id,
                version_id=invocation.version_id,
                outcome=outcome,
                summary=summary,
                action_link_ids=[link.id for link in links if link.id is not None],
            )
        )
        invocation.outcome_id = feedback.id
        invocation.finished_at = datetime.now(UTC)
        if outcome is ProcedureOutcome.SUCCEEDED:
            invocation.state = InvocationState.COMPLETED
        elif outcome is ProcedureOutcome.ABANDONED:
            invocation.state = InvocationState.CANCELLED
        else:
            invocation.state = InvocationState.FAILED
        await self._store.save_invocation(invocation)
        await ProcedureAdmissionService(self._store).ingest_activation_feedback(feedback)
        return feedback
