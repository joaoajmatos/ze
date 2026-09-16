from __future__ import annotations

from uuid import uuid4

from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    ProcedureFeedback,
    ProcedureIdentity,
    ProcedureOutcome,
    ProcedureVersion,
    VersionStatus,
)
from ze_agents.claims import Provenance


async def test_one_active_version_per_identity() -> None:
    store = InMemoryProcedureStore()
    identity = await store.save_identity(ProcedureIdentity(canonical_name="loops"))
    v1 = await store.save_version(
        ProcedureVersion(
            procedure_id=identity.id,
            version_number=1,
            name="loops",
            trigger="t",
            preconditions=[],
            steps=["a"],
            success_criteria=["done"],
            provenance=Provenance.SYNTHESIZED,
        )
    )
    v2 = await store.save_version(
        ProcedureVersion(
            procedure_id=identity.id,
            version_number=2,
            name="loops",
            trigger="t",
            preconditions=[],
            steps=["a", "b"],
            success_criteria=["done"],
            provenance=Provenance.SYNTHESIZED,
        )
    )
    v1.status = VersionStatus.SUPERSEDED
    await store.save_version(v1)
    identity.active_version_id = v2.id
    await store.save_identity(identity)
    active = await store.list_active_versions()
    assert [row.id for row in active] == [v2.id]


async def test_feedback_is_append_only() -> None:
    store = InMemoryProcedureStore()
    identity = await store.save_identity(ProcedureIdentity(canonical_name="loops"))
    version = await store.save_version(
        ProcedureVersion(
            procedure_id=identity.id,
            version_number=1,
            name="loops",
            trigger="t",
            preconditions=[],
            steps=["a"],
            success_criteria=["done"],
            provenance=Provenance.SYNTHESIZED,
        )
    )
    first = await store.save_feedback(
        ProcedureFeedback(
            procedure_version_id=version.id,
            action_record_id=uuid4(),
            outcome=ProcedureOutcome.SUCCEEDED,
            summary="worked",
        )
    )
    second = await store.save_feedback(
        ProcedureFeedback(
            procedure_version_id=version.id,
            action_record_id=uuid4(),
            outcome=ProcedureOutcome.FAILED,
            summary="later failed",
        )
    )
    rows = await store.list_feedback(version.id)
    assert [row.id for row in rows] == [first.id, second.id]
    loaded = await store.get_version(version.id)
    assert loaded.steps == ["a"]
