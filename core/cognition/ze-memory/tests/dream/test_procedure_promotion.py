from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_memory.dream.promoter import DreamPromoter
from ze_memory.dream.types import ArtifactType
from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.store import InMemoryProcedureStore


class _AsyncCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass


def _make_pool():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": uuid4()})
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    return pool, conn


async def test_dream_procedure_submits_reviewed_candidate() -> None:
    pool, conn = _make_pool()
    store = InMemoryProcedureStore()
    service = ProcedureAdmissionService(store)
    promoter = DreamPromoter(
        pool=pool,
        dream_store=AsyncMock(),
        embedder=None,
        procedure_admission=service,
    )
    artifact_id = uuid4()
    await promoter._promote(
        {
            "id": artifact_id,
            "artifact_type": ArtifactType.SYNTHESIZED_PROCEDURE.value,
            "content": "Draft, wait, send",
        },
        run_id=uuid4(),
        valid_days=90,
    )
    conn.fetchrow.assert_not_awaited()
    candidates = await store.list_candidates()
    assert len(candidates) == 1
    assert candidates[0].source_kind.value == "reflection"
    assert candidates[0].evidence_refs[0].id == artifact_id
    assert await service.retrieve_procedures() == []
