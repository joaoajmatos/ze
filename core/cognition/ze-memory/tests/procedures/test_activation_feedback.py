from __future__ import annotations

from uuid import uuid4

from ze_agents.claims import Provenance
from ze_memory.procedures.activation import ProcedureActivator
from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    LifecycleEventKind,
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureOutcome,
    ProcedureSourceKind,
    VersionStatus,
)
from ze_plugin.contribution import EvidenceRef


async def test_complete_does_not_change_version_status() -> None:
    store = InMemoryProcedureStore()
    service = ProcedureAdmissionService(store)
    saved = await service.submit_procedure_candidate(
        ProcedureCandidate(
            source_kind=ProcedureSourceKind.USER_INSTRUCTION,
            provenance=Provenance.PROMPT_SUPPLIED,
            name="Inbox sweep",
            trigger="clear inbox",
            preconditions=[],
            steps=["open inbox"],
            success_criteria=["done"],
            evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        )
    )
    admitted = await service.review_procedure_candidate(
        saved.id, ProcedureAdmissionDecision.APPROVE, reason="ok"
    )
    from ze_memory.procedures.discovery import ProcedureDiscovery
    from ze_memory.procedures.types import (
        MatchState,
        ProcedureInvocationOrigin,
        ProcedureTaskContext,
    )

    matches = await ProcedureDiscovery(store).match(
        ProcedureTaskContext(caller="t", task_text="clear inbox"),
        agent_allowed_tools=frozenset(),
        capability_allowed_tools=frozenset(),
    )
    ready = [m for m in matches if m.state is MatchState.READY][0]
    activator = ProcedureActivator(store)
    invocation = await activator.invoke(
        ready, origin=ProcedureInvocationOrigin.AGENT, caller="t"
    )
    await activator.complete(
        invocation.id, outcome=ProcedureOutcome.FAILED, summary="bounced"
    )
    version = await store.get_version(admitted.version.id)
    assert version.status is VersionStatus.ACTIVE
    events = await store.list_events(identity_id=admitted.identity.id)
    kinds = {event.kind for event in events}
    assert LifecycleEventKind.FEEDBACK_RECORDED in kinds
    assert LifecycleEventKind.REVIEWED in kinds
