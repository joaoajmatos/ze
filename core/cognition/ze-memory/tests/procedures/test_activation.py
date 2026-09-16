from __future__ import annotations

from uuid import uuid4

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.activation import ProcedureActivator
from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.discovery import ProcedureDiscovery
from ze_memory.procedures.errors import BlockedProcedureError, IneligibleProcedureError
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    CapabilityDecision,
    MatchState,
    ProcedureActionOutcome,
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureInvocationOrigin,
    ProcedureOutcome,
    ProcedureSourceKind,
    ProcedureTaskContext,
    VersionStatus,
)


async def _ready_match(store):
    service = ProcedureAdmissionService(store)
    saved = await service.submit_procedure_candidate(
        ProcedureCandidate(
            source_kind=ProcedureSourceKind.USER_INSTRUCTION,
            provenance=Provenance.PROMPT_SUPPLIED,
            name="Inbox sweep",
            trigger="clear the morning inbox",
            preconditions=["inbox is connected"],
            steps=["open inbox"],
            success_criteria=["inbox triaged"],
            limits=["search_email"],
            evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        )
    )
    await service.review_procedure_candidate(
        saved.id, ProcedureAdmissionDecision.APPROVE, reason="ok"
    )
    matches = await ProcedureDiscovery(store).match(
        ProcedureTaskContext(
            caller="companion",
            task_text="clear the morning inbox",
            available_facts=["inbox is connected"],
        ),
        agent_allowed_tools=frozenset({"search_email"}),
        capability_allowed_tools=frozenset({"search_email"}),
    )
    return [m for m in matches if m.state is MatchState.READY][0]


async def test_invoke_records_immutable_version_and_action_links() -> None:
    store = InMemoryProcedureStore()
    match = await _ready_match(store)
    activator = ProcedureActivator(store)
    invocation = await activator.invoke(
        match, origin=ProcedureInvocationOrigin.AGENT, caller="companion"
    )
    link = await activator.record_action(
        invocation.id,
        step_ref="step-1",
        action_trace_ref="trace-1",
        capability_decision=CapabilityDecision.ALLOWED,
        outcome=ProcedureActionOutcome.SUCCEEDED,
    )
    denied = await activator.record_action(
        invocation.id,
        step_ref="step-2",
        action_trace_ref="trace-2",
        capability_decision=CapabilityDecision.DENIED,
        outcome=ProcedureActionOutcome.NOT_EXECUTED,
    )
    assert link.version_id == match.version_id
    assert denied.outcome is ProcedureActionOutcome.NOT_EXECUTED
    version = await store.get_version(match.version_id)
    assert version.status is VersionStatus.ACTIVE


async def test_complete_is_idempotent_and_does_not_mutate_version() -> None:
    store = InMemoryProcedureStore()
    match = await _ready_match(store)
    activator = ProcedureActivator(store)
    invocation = await activator.invoke(
        match, origin=ProcedureInvocationOrigin.AGENT, caller="companion"
    )
    first = await activator.complete(
        invocation.id, outcome=ProcedureOutcome.FAILED, summary="send bounced"
    )
    second = await activator.complete(
        invocation.id, outcome=ProcedureOutcome.SUCCEEDED, summary="ignored"
    )
    assert first.id == second.id
    assert second.outcome is ProcedureOutcome.FAILED
    version = await store.get_version(match.version_id)
    assert version.status is VersionStatus.ACTIVE
    assert version.steps == ["open inbox"]


async def test_blocked_match_cannot_invoke() -> None:
    store = InMemoryProcedureStore()
    match = await _ready_match(store)
    match.state = MatchState.BLOCKED
    activator = ProcedureActivator(store)
    try:
        await activator.invoke(
            match, origin=ProcedureInvocationOrigin.AGENT, caller="companion"
        )
        raise AssertionError("blocked match must not invoke")
    except BlockedProcedureError:
        pass


async def test_disabled_procedure_cannot_invoke() -> None:
    store = InMemoryProcedureStore()
    match = await _ready_match(store)
    await ProcedureAdmissionService(store).disable_procedure(
        match.procedure_id, reason="stop"
    )
    activator = ProcedureActivator(store)
    try:
        await activator.invoke(
            match, origin=ProcedureInvocationOrigin.AGENT, caller="companion"
        )
        raise AssertionError("disabled procedure must not invoke")
    except IneligibleProcedureError:
        pass
