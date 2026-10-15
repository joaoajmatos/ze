from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from ze_agents.claims import Provenance
from ze_ingestion.sink import MemorySink
from ze_plugin.contribution import EvidenceRef, TargetFace


@pytest.fixture
def memory_store() -> AsyncMock:
    return AsyncMock()


async def test_push_empty_facts_is_noop(memory_store: AsyncMock) -> None:
    sink = MemorySink(memory_store)
    with patch(
        "ze_ingestion.sink.submit_perception_facts", new_callable=AsyncMock
    ) as submit:
        await sink.push(ingestion_id=str(uuid4()), facts=[])
    submit.assert_not_awaited()
    memory_store.propose_facts.assert_not_called()


async def test_push_uuid_ingestion_id_on_source_refs_and_evidence(
    memory_store: AsyncMock,
) -> None:
    sink = MemorySink(memory_store)
    ingest_id = uuid4()
    with patch(
        "ze_ingestion.sink.submit_perception_facts", new_callable=AsyncMock
    ) as submit:
        await sink.push(
            ingestion_id=str(ingest_id),
            facts=["Python is popular.", "It runs on CPython."],
        )
    memory_store.propose_facts.assert_not_called()
    submit.assert_awaited_once()
    items = submit.await_args.args[1]
    assert len(items) == 2
    for item in items:
        assert item.provenance == Provenance.SYNTHESIZED
        assert item.target_face == TargetFace.WORLD
        assert item.fact.source_refs == [ingest_id]
        assert len(item.evidence) == 1
        assert item.evidence[0].kind == "ingestion"
        assert item.evidence[0].id == ingest_id
        assert isinstance(item.evidence[0].id, UUID)


async def test_push_does_not_call_ungated_propose_facts(
    memory_store: AsyncMock,
) -> None:
    sink = MemorySink(memory_store)
    with patch(
        "ze_ingestion.sink.submit_perception_facts", new_callable=AsyncMock
    ) as submit:
        await sink.push(ingestion_id=str(uuid4()), facts=["A fact."])
    memory_store.propose_facts.assert_not_called()
    submit.assert_awaited_once()


async def test_push_memory_store_exception_is_caught(memory_store: AsyncMock) -> None:
    sink = MemorySink(memory_store)
    with patch(
        "ze_ingestion.sink.submit_perception_facts",
        new_callable=AsyncMock,
        side_effect=RuntimeError("DB down"),
    ):
        await sink.push(ingestion_id=str(uuid4()), facts=["A fact."])


async def test_push_forwards_ingestion_evidence_to_loop_extractor(
    memory_store: AsyncMock,
) -> None:
    sink = MemorySink(memory_store)
    extractor = AsyncMock()
    sink.loop_extractor = extractor
    ingest_id = uuid4()
    with patch("ze_ingestion.sink.submit_perception_facts", new_callable=AsyncMock):
        await sink.push(ingestion_id=str(ingest_id), facts=["Python is popular."])

    extractor.assert_awaited_once_with(
        "Python is popular.",
        "ingestion",
        evidence=[EvidenceRef(kind="ingestion", id=ingest_id)],
    )


async def test_push_non_uuid_forwards_empty_evidence(memory_store: AsyncMock) -> None:
    sink = MemorySink(memory_store)
    extractor = AsyncMock()
    sink.loop_extractor = extractor
    with patch("ze_ingestion.sink.submit_perception_facts", new_callable=AsyncMock):
        await sink.push(ingestion_id="not-a-uuid", facts=["A fact."])

    extractor.assert_awaited_once_with("A fact.", "ingestion", evidence=[])
