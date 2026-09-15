from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from ze_agents.claims import Provenance
from ze_logging import get_logger
from ze_memory.contribution import PerceptionFactSubmit, submit_perception_facts
from ze_memory.types import Fact
from ze_plugin.contribution import EvidenceRef, TargetFace

log = get_logger(__name__)


class MemorySink:
    """Pushes extracted facts into ze-memory."""

    def __init__(
        self,
        memory_store: Any,
        loop_extractor: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        self._store = memory_store
        # Optional hook wired post-construction by ze-api (open-loop extraction,
        # FR-008's ingestion inflow) — kept generic here so ze-ingestion has no
        # dependency on ze-worldstate (plan.md: ze-api is the only wiring point).
        self.loop_extractor = loop_extractor

    async def push(self, ingestion_id: str, facts: list[str]) -> None:
        if not facts:
            return
        evidence: list[EvidenceRef] = []
        source_refs: list[UUID] = []
        try:
            ingest_uuid = UUID(ingestion_id)
            evidence = [EvidenceRef(kind="ingestion", id=ingest_uuid)]
            source_refs = [ingest_uuid]
        except ValueError:
            log.warning(
                "memory_sink_non_uuid_ingestion_id",
                ingestion_id=ingestion_id,
            )
        items = [
            PerceptionFactSubmit(
                fact=Fact(
                    predicate=text,
                    value=(
                        text
                        if source_refs
                        else f"{text} [ingestion:{ingestion_id}]"
                    ),
                    source_refs=list(source_refs),
                ),
                provenance=Provenance.SYNTHESIZED,
                target_face=TargetFace.WORLD,
                evidence=list(evidence),
            )
            for text in facts
        ]
        try:
            await submit_perception_facts(self._store, items)
            log.info("memory_sink_pushed", ingestion_id=ingestion_id, count=len(facts))
        except Exception as exc:
            log.warning("memory_sink_failed", ingestion_id=ingestion_id, error=str(exc))

        if self.loop_extractor is not None:
            try:
                await self.loop_extractor(". ".join(facts), "ingestion")
            except Exception as exc:
                log.warning(
                    "ingestion_loop_extraction_failed",
                    ingestion_id=ingestion_id,
                    error=str(exc),
                )
