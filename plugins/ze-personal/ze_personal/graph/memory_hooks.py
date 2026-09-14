"""Contact extraction memory hook.

Transitional location — will move to ze_personal/graph/memory_hooks.py once
the ze-personal package is created (arch-package-reorg step 4).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from ze_agents.claims import Confidence, DecayProfile
from ze_memory.graph.predicates import WORKS_ON
from ze_memory.graph.types import Relationship
from ze_memory.types import Entity
from ze_sdk.channels import ChannelHandle, ChannelType
from ze_sdk.contribution import submit_and_detect_collisions

from ze_personal.contacts.contribution import person_source_to_contribution
from ze_personal.contacts.types import (
    ContactProposal,
    Person,
    PersonSource,
    ProjectProposal,
    RelationshipEdgeProposal,
)
from ze_logging import get_logger

log = get_logger(__name__)


async def contact_proposal_hook(result: Any, ctx: Any, config: dict) -> None:
    """Write contact/project/relationship proposals from an agent result into
    the person store and memory graph.

    Reads person_store, contact_channel_store, and memory_store from
    config["configurable"]. No-op when the relevant store is absent or result
    has no proposals of that kind.
    """
    person_store = config["configurable"].get("person_store")
    contact_channel_store = config["configurable"].get("contact_channel_store")
    collision_store = config["configurable"].get("collision_store")
    nli_client = config["configurable"].get("nli_client")
    memory_store = config["configurable"].get("memory_store")
    if person_store and result.contact_proposals:
        await _write_contact_proposals(
            person_store,
            result.contact_proposals,
            ctx.prompt,
            contact_channel_store=contact_channel_store,
            collision_store=collision_store,
            nli_client=nli_client,
        )
    if memory_store is not None:
        for proposal in result.extensions.get("project_proposals") or []:
            await _write_project_entity(memory_store, proposal)
        for edge in result.extensions.get("relationship_edge_proposals") or []:
            await _write_relationship_edge(memory_store, edge)


async def _write_project_entity(
    memory_store: Any, proposal: ProjectProposal
) -> UUID | None:
    """Upsert a `project` entity, mirroring PersonStore._write_entity()'s pattern."""
    if not proposal.name:
        return None
    entity = Entity(
        id=None,
        entity_type="project",
        canonical_name=proposal.name,
        aliases=[],
        attrs={},
    )
    try:
        return await memory_store.upsert_entity(entity)
    except Exception as exc:
        log.warning("project_entity_write_failed", name=proposal.name, error=str(exc))
        return None


async def _write_relationship_edge(
    memory_store: Any, edge: RelationshipEdgeProposal
) -> None:
    """Upsert a WORKS_ON/COLLABORATES_WITH edge between find-or-created entities."""
    if not edge.person_name or not edge.target_name:
        return
    graph_store = getattr(memory_store, "graph_store", None)
    if graph_store is None:
        return
    target_type = "project" if edge.predicate == WORKS_ON else "person"
    try:
        source_id = await memory_store.upsert_entity(
            Entity(
                id=None,
                entity_type="person",
                canonical_name=edge.person_name,
                aliases=[],
                attrs={},
            )
        )
        target_id = await memory_store.upsert_entity(
            Entity(
                id=None,
                entity_type=target_type,
                canonical_name=edge.target_name,
                aliases=[],
                attrs={},
            )
        )
        await graph_store.upsert_relationship(
            Relationship(
                source_id=source_id,
                source_type="person",
                predicate=edge.predicate,
                target_id=target_id,
                target_type=target_type,
                confidence=Confidence(
                    value=edge.confidence, decay_profile=DecayProfile.TIME_LINEAR
                ),
            )
        )
    except Exception as exc:
        log.warning(
            "relationship_edge_write_failed",
            predicate=edge.predicate,
            person=edge.person_name,
            target=edge.target_name,
            error=str(exc),
        )


async def _write_contact_proposals(
    person_store: Any,
    proposals: list[ContactProposal],
    prompt: str,
    contact_channel_store: Any = None,
    collision_store: Any = None,
    nli_client: Any = None,
) -> None:
    for proposal in proposals:
        if not proposal.name:
            continue
        try:
            existing = await person_store.get_by_name(proposal.name)
            source = PersonSource(
                person_id=None,  # type: ignore[arg-type]  — replaced below
                source_type=proposal.source_type,
                weight=proposal.confidence,
                raw_context=prompt[:300],
            )
            if existing:
                best = existing[0]
                source.person_id = best.id
                await submit_and_detect_collisions(
                    person_source_to_contribution(source),
                    lambda: person_store.add_source(best.id, source),
                    result_id=lambda _: best.id,
                    producer_kind="contact",
                    collision_store=collision_store,
                    nli_client=nli_client,
                )
                contact_id = best.id
            else:
                person = Person(
                    name=proposal.name,
                    classification=proposal.classification,
                    classification_confidence=proposal.confidence,
                    relationship_to_user=proposal.relationship,
                    contact_info=proposal.contact_info,
                    confirmed=proposal.confirmed,
                    dismissed=False,
                    confidence=proposal.confidence,
                )

                async def _write() -> Person:
                    stored = await person_store.upsert(person)
                    source.person_id = stored.id
                    await person_store.add_source(stored.id, source)
                    return stored

                stored = await submit_and_detect_collisions(
                    person_source_to_contribution(source),
                    _write,
                    result_id=lambda p: p.id,
                    producer_kind="contact",
                    collision_store=collision_store,
                    nli_client=nli_client,
                )
                contact_id = stored.id

            if contact_channel_store:
                await _write_channel_handles(
                    contact_channel_store, contact_id, proposal
                )

        except Exception as exc:
            log.warning(
                "contact_proposal_write_failed", name=proposal.name, error=str(exc)
            )


async def _write_channel_handles(
    store: Any,
    contact_id: Any,
    proposal: ContactProposal,
) -> None:
    email_addr = proposal.contact_info.get("email", "").strip().lower()
    if email_addr:
        try:
            await store.upsert(
                contact_id,
                ChannelHandle(
                    channel_type=ChannelType.EMAIL,
                    handle=email_addr,
                ),
            )
        except Exception as exc:
            log.warning(
                "contact_channel_write_failed",
                contact_id=str(contact_id),
                error=str(exc),
            )
