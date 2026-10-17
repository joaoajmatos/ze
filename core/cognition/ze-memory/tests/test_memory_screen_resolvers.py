from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind, Provenance
from ze_agents.screen import ResolveContext, ScreenRef, ScreenStatus
from ze_memory.procedures.types import (
    IdentityStatus,
    ProcedureIdentity,
    ProcedureVersion,
    VersionStatus,
)
from ze_memory.screen_resolvers import (
    EntityScreenResolver,
    FactScreenResolver,
    ProcedureScreenResolver,
    build_screen_resolvers,
)
from ze_memory.types import Entity, Fact

CTX = ResolveContext(now=datetime(2026, 10, 17, tzinfo=UTC))


async def test_entity_line_names_type_and_capped_relations():
    eid = uuid4()
    entity = Entity(
        id=eid,
        entity_type="person",
        canonical_name="Ana Costa",
        attrs={"last_contact": "2026-10-10"},
    )
    rels = [SimpleNamespace(predicate=f"works_on_{i}") for i in range(8)] + [
        SimpleNamespace(predicate="works_on_0")
    ]
    retriever, graph = AsyncMock(), AsyncMock()
    retriever.get_entity = AsyncMock(return_value=entity)
    graph.expand = AsyncMock(return_value=SimpleNamespace(relationships=rels))
    [line] = await EntityScreenResolver(retriever, graph).resolve(
        [ScreenRef(kind="entity", id=str(eid))], CTX
    )
    assert line.label == "Ana Costa" and line.status is ScreenStatus.OK
    assert "person" in line.summary and "last contact 2026-10-10" in line.summary
    assert line.summary.count("works on") == 5  # capped at five, deduped
    graph.expand.assert_awaited_once()
    assert graph.expand.await_args.kwargs["max_hops"] == 1


async def test_entity_survives_a_graph_failure_and_reports_missing():
    eid = uuid4()
    retriever, graph = AsyncMock(), AsyncMock()
    retriever.get_entity = AsyncMock(
        return_value=Entity(id=eid, entity_type="project", canonical_name="LedgerLite")
    )
    graph.expand = AsyncMock(side_effect=RuntimeError("x"))
    [line] = await EntityScreenResolver(retriever, graph).resolve(
        [ScreenRef(kind="entity", id=str(eid))], CTX
    )
    assert line.status is ScreenStatus.OK and "project" in line.summary
    retriever.get_entity = AsyncMock(return_value=None)
    [line] = await EntityScreenResolver(retriever, graph).resolve(
        [ScreenRef(kind="entity", id=str(eid))], CTX
    )
    assert line.status is ScreenStatus.MISSING


async def test_fact_line_is_a_sentence_never_the_raw_key_with_record_posture():
    fid = uuid4()
    fact = Fact(
        predicate="prefers_morning_meetings",
        value="Prefers mornings",
        id=fid,
        confidence=0.7,
        reviewed=True,
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.PROMPT_SUPPLIED,
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    retriever = AsyncMock()
    retriever.get_facts_by_ids = AsyncMock(return_value=[fact])
    [line] = await FactScreenResolver(retriever).resolve(
        [ScreenRef(kind="fact", id=str(fid), label="bogus")], CTX
    )
    assert "prefers_morning_meetings" not in line.summary
    assert (
        "prefers morning meetings: Prefers mornings" in line.summary
        and "reviewed" in line.summary
    )
    assert (line.posture.kind, line.posture.confidence) == (ClaimKind.FACT, 0.7)
    retriever.get_facts_by_ids = AsyncMock(return_value=[])
    [gone] = await FactScreenResolver(retriever).resolve(
        [ScreenRef(kind="fact", id=str(fid))], CTX
    )
    assert gone.status is ScreenStatus.MISSING


async def test_procedure_line_uses_identity_and_active_version():
    pid, vid = uuid4(), uuid4()
    identity = ProcedureIdentity(
        canonical_name="Weekly review",
        id=pid,
        active_version_id=vid,
        status=IdentityStatus.ACTIVE,
    )
    version = ProcedureVersion(
        procedure_id=pid,
        version_number=3,
        name="Weekly review",
        trigger="t",
        preconditions=[],
        steps=["a", "b"],
        success_criteria=[],
        provenance=Provenance.SYNTHESIZED,
        status=VersionStatus.ACTIVE,
        id=vid,
    )
    store = AsyncMock()
    store.get_identity = AsyncMock(return_value=identity)
    store.list_versions = AsyncMock(return_value=[version])
    [line] = await ProcedureScreenResolver(store).resolve(
        [ScreenRef(kind="procedure", id=str(pid))], CTX
    )
    assert (
        line.label == "Weekly review"
        and "version 3 (active)" in line.summary
        and "2 steps" in line.summary
    )
    store.get_identity = AsyncMock(return_value=None)
    [gone] = await ProcedureScreenResolver(store).resolve(
        [ScreenRef(kind="procedure", id=str(pid))], CTX
    )
    assert gone.status is ScreenStatus.MISSING


def test_factory_kinds():
    kinds = {
        k
        for r in build_screen_resolvers(
            retriever=AsyncMock(), graph_store=AsyncMock(), procedure_store=AsyncMock()
        )
        for k in r.kinds
    }
    assert kinds == {"entity", "fact", "procedure"}
