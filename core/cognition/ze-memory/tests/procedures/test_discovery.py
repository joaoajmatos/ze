from __future__ import annotations

from uuid import uuid4

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.discovery import ProcedureDiscovery, intersect_tools
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    MatchState,
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureSourceKind,
    ProcedureTaskContext,
)


async def _admitted(store, **overrides):
    service = ProcedureAdmissionService(store)
    base = dict(
        source_kind=ProcedureSourceKind.USER_INSTRUCTION,
        provenance=Provenance.PROMPT_SUPPLIED,
        name="Inbox sweep",
        trigger="clear the morning inbox",
        preconditions=["inbox is connected"],
        steps=["open inbox", "archive promotions"],
        success_criteria=["inbox triaged"],
        limits=["search_email", "archive_email"],
        evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
    )
    base.update(overrides)
    saved = await service.submit_procedure_candidate(ProcedureCandidate(**base))
    return await service.review_procedure_candidate(
        saved.id, ProcedureAdmissionDecision.APPROVE, reason="ok"
    )


async def test_match_returns_ready_when_trigger_and_preconditions_hold() -> None:
    store = InMemoryProcedureStore()
    admitted = await _admitted(store)
    discovery = ProcedureDiscovery(store)
    matches = await discovery.match(
        ProcedureTaskContext(
            caller="planner",
            task_text="Please clear the morning inbox today",
            available_facts=["inbox is connected"],
        ),
        agent_allowed_tools=frozenset({"search_email", "archive_email", "browser"}),
        capability_allowed_tools=frozenset({"search_email", "archive_email"}),
    )
    assert len(matches) == 1
    assert matches[0].state is MatchState.READY
    assert matches[0].version_id == admitted.version.id
    assert matches[0].effective_tool_names == frozenset(
        {"search_email", "archive_email"}
    )


async def test_unmet_precondition_is_blocked_not_ready() -> None:
    store = InMemoryProcedureStore()
    await _admitted(store)
    discovery = ProcedureDiscovery(store)
    matches = await discovery.match(
        ProcedureTaskContext(
            caller="planner",
            task_text="Please clear the morning inbox today",
            available_facts=[],
        ),
        agent_allowed_tools=frozenset({"search_email"}),
        capability_allowed_tools=frozenset({"search_email"}),
    )
    assert matches[0].state is MatchState.BLOCKED
    assert matches[0].unmet_preconditions == ["inbox is connected"]


async def test_disabled_procedure_is_not_actionable() -> None:
    store = InMemoryProcedureStore()
    admitted = await _admitted(store)
    await ProcedureAdmissionService(store).disable_procedure(
        admitted.identity.id, reason="unsafe"
    )
    discovery = ProcedureDiscovery(store)
    matches = await discovery.match(
        ProcedureTaskContext(
            caller="planner",
            task_text="Please clear the morning inbox today",
            available_facts=["inbox is connected"],
        ),
        agent_allowed_tools=frozenset({"search_email"}),
        capability_allowed_tools=frozenset({"search_email"}),
    )
    assert matches == []


def test_tool_intersection_never_expands() -> None:
    effective = intersect_tools(
        frozenset({"search_email", "send_email"}),
        frozenset({"search_email"}),
        frozenset({"search_email", "browser"}),
    )
    assert effective == frozenset({"search_email"})
    assert "send_email" not in effective
    assert "browser" not in effective


def test_empty_procedure_relevant_does_not_lock_tools() -> None:
    effective = intersect_tools(
        frozenset({"search_email", "send_email"}),
        frozenset({"search_email", "send_email"}),
        frozenset(),
    )
    assert effective == frozenset({"search_email", "send_email"})
