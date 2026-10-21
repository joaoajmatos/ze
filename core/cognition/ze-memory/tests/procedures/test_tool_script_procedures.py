from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures import tools as procedure_tools
from ze_memory.procedures.activation import ProcedureActivator
from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.discovery import ProcedureDiscovery, format_procedure_guidance
from ze_memory.procedures.errors import (
    IncompleteProcedureCandidateError,
    InvalidProcedureEvidenceError,
)
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    MatchState,
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureSourceKind,
    ProcedureTaskContext,
)
from ze_memory.procedures.validate import validate_candidate


def _candidate(kind=ProcedureSourceKind.TOOL_SCRIPT, **overrides) -> ProcedureCandidate:
    base = dict(
        source_kind=kind,
        provenance=Provenance.SYNTHESIZED,
        name="Script: get_a → get_b [abcd1234]",
        trigger="top merchants this month",
        preconditions=[],
        steps=["z.finish(1)"],
        success_criteria=["script ends ok"],
        limits=["get_a", "get_b"],
        evidence_refs=[EvidenceRef(kind="action_record", id=uuid4())],
    )
    base.update(overrides)
    return ProcedureCandidate(**base)


async def _admit(store, candidate):
    service = ProcedureAdmissionService(store)
    saved = await service.submit_procedure_candidate(candidate)
    await service.review_procedure_candidate(
        saved.id, ProcedureAdmissionDecision.APPROVE, reason="ok"
    )


async def _matches(store, text="top merchants this month"):
    return await ProcedureDiscovery(store).match(
        ProcedureTaskContext(caller="finance", task_text=text),
        agent_allowed_tools=frozenset({"get_a", "get_b"}),
        capability_allowed_tools=frozenset({"get_a", "get_b"}),
    )


class CountingStore(InMemoryProcedureStore):
    def __init__(self) -> None:
        super().__init__()
        self.calls: dict[str, int] = {}

    def __getattribute__(self, name):
        if name.startswith(("get_", "list_", "find_")):
            calls = object.__getattribute__(self, "calls")
            calls[name] = calls.get(name, 0) + 1
        return object.__getattribute__(self, name)


async def test_list_active_versions_carries_source_kind_without_extra_queries():
    store = CountingStore()
    await _admit(store, _candidate())
    await _admit(
        store,
        _candidate(
            ProcedureSourceKind.USER_INSTRUCTION, name="Inbox", evidence_refs=[]
        ),
    )
    store.calls.clear()
    versions = await store.list_active_versions()
    kinds = {v.name: v.source_kind for v in versions}
    assert kinds == {
        "Script: get_a → get_b [abcd1234]": "tool_script",
        "Inbox": "user_instruction",
    }
    assert store.calls == {"list_active_versions": 1}


async def test_version_without_admission_has_no_source_kind():
    store = InMemoryProcedureStore()
    from ze_memory.procedures.types import ProcedureIdentity, ProcedureVersion

    identity = await store.save_identity(ProcedureIdentity(canonical_name="x"))
    await store.save_version(
        ProcedureVersion(
            procedure_id=identity.id,
            version_number=1,
            name="x",
            trigger="t",
            preconditions=[],
            steps=["a"],
            success_criteria=["d"],
            provenance=Provenance.SYNTHESIZED,
        )
    )
    assert [v.source_kind for v in await store.list_active_versions()] == [None]


async def test_candidate_exists_by_name_in_any_status():
    store = InMemoryProcedureStore()
    service = ProcedureAdmissionService(store)
    assert await service.candidate_exists("Script: a") is False
    await service.submit_procedure_candidate(_candidate(name="Script: a"))
    assert await service.candidate_exists("Script: a") is True
    assert await store.candidate_exists("Script: a") is True
    assert await service.candidate_exists("Script: b") is False


async def test_discovery_fills_source_kind_and_guidance_is_one_line():
    store = InMemoryProcedureStore()
    await _admit(store, _candidate())
    [match] = await _matches(store)
    assert match.source_kind == "tool_script"
    assert match.state is MatchState.READY
    guidance = format_procedure_guidance([match])
    assert guidance is not None
    line = f"- [ready] {match.name} id={match.procedure_id}: script procedure, run it with run_tool_script(procedure_id=\"{match.procedure_id}\")"
    assert line in guidance
    assert "z.finish" not in guidance
    assert "steps:" not in guidance
    assert "trigger:" not in guidance


async def test_other_matches_keep_their_steps_in_guidance():
    store = InMemoryProcedureStore()
    await _admit(
        store,
        _candidate(
            ProcedureSourceKind.USER_INSTRUCTION,
            name="Inbox",
            steps=["open inbox"],
            evidence_refs=[],
        ),
    )
    [match] = await _matches(store)
    assert match.source_kind == "user_instruction"
    assert "steps: open inbox" in format_procedure_guidance([match])


def test_validate_tool_script_requires_evidence_one_step_and_a_size_cap():
    validate_candidate(_candidate())
    with pytest.raises(InvalidProcedureEvidenceError):
        validate_candidate(_candidate(evidence_refs=[]))
    with pytest.raises(IncompleteProcedureCandidateError):
        validate_candidate(_candidate(steps=["a", "b"]))
    with pytest.raises(IncompleteProcedureCandidateError):
        validate_candidate(_candidate(steps=["x" * 8001]))
    validate_candidate(_candidate(steps=["x" * 8000]))


async def test_invoke_procedure_on_a_script_records_and_points_to_run_tool_script(
    monkeypatch,
):
    store = InMemoryProcedureStore()
    await _admit(store, _candidate())
    [match] = await _matches(store)
    activator = ProcedureActivator(store)
    monkeypatch.setattr(procedure_tools, "_activator", activator)
    ctx = SimpleNamespace(procedure_matches=[match], session_id="s1")
    out = await procedure_tools.invoke_procedure(str(match.procedure_id), ctx=ctx)
    assert out == (
        "This is a script procedure: run it with "
        f'run_tool_script(procedure_id="{match.procedure_id}").'
    )
    assert ctx.procedure_invocation_id
    assert len(store.invocations) == 1
