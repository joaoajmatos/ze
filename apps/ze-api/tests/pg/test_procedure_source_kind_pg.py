from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from ze_agents.claims import Provenance
from ze_api.wiring.db import _init_conn
from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.store import PostgresProcedureStore
from ze_memory.procedures.types import (
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureIdentity,
    ProcedureSourceKind,
    ProcedureVersion,
)
from ze_plugin.contribution import EvidenceRef

pytestmark = pytest.mark.pg


@pytest_asyncio.fixture
async def app_pool(pg_dsn):
    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=2, init=_init_conn)
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE procedure_versions, procedure_admissions, procedure_candidates, "
            "procedure_identities CASCADE"
        )
    yield pool
    await pool.close()


def _candidate(kind, name):
    return ProcedureCandidate(
        source_kind=kind,
        provenance=Provenance.SYNTHESIZED,
        name=name,
        trigger="t",
        preconditions=[],
        steps=["z.finish(1)"],
        success_criteria=["ok"],
        evidence_refs=[EvidenceRef(kind="action_record", id=uuid4())],
    )


async def test_active_versions_carry_source_kind_through_one_join(app_pool):
    store = PostgresProcedureStore(app_pool)
    service = ProcedureAdmissionService(store)
    for kind, name in (
        (ProcedureSourceKind.TOOL_SCRIPT, "Script: a [1]"),
        (ProcedureSourceKind.USER_INSTRUCTION, "Inbox"),
    ):
        saved = await service.submit_procedure_candidate(_candidate(kind, name))
        await service.review_procedure_candidate(
            saved.id, ProcedureAdmissionDecision.APPROVE, reason="ok"
        )
    identity = await store.save_identity(ProcedureIdentity(canonical_name="orphan"))
    await store.save_version(
        ProcedureVersion(
            procedure_id=identity.id,
            version_number=1,
            name="orphan",
            trigger="t",
            preconditions=[],
            steps=["a"],
            success_criteria=["d"],
            provenance=Provenance.SYNTHESIZED,
        )
    )

    kinds = {v.name: v.source_kind for v in await store.list_active_versions()}
    assert kinds == {
        "Script: a [1]": "tool_script",
        "Inbox": "user_instruction",
        "orphan": None,
    }
    assert await store.candidate_exists("Script: a [1]") is True
    assert await store.candidate_exists("nope") is False
