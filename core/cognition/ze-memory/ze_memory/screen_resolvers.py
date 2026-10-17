"""Screen resolvers for entities, facts and procedures (phase 195)."""

from __future__ import annotations

from typing import Any

from ze_agents.screen import (
    ResolveContext,
    ScreenLine,
    ScreenPosture,
    ScreenRef,
    ScreenResolver,
    as_utc,
    parse_uuid,
    resolve_each,
    sanitize_text,
)

MAX_RELATIONS = 5


def _words(value: Any) -> str:
    return str(getattr(value, "value", value)).replace("_", " ")


class EntityScreenResolver:
    kinds = frozenset({"entity"})

    def __init__(self, retriever: Any, graph_store: Any) -> None:
        self._retriever = retriever
        self._graph = graph_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, self._load)

    async def _load(self, ref: ScreenRef) -> ScreenLine | None:
        entity_id = parse_uuid(ref.id)
        entity = await self._retriever.get_entity(entity_id) if entity_id else None
        if entity is None:
            return None
        parts = [_words(entity.entity_type)]
        try:
            expansion = await self._graph.expand(
                [entity_id], max_hops=1, limit=MAX_RELATIONS * 2
            )
            names = []
            for rel in expansion.relationships:
                name = _words(rel.predicate)
                if name not in names:
                    names.append(name)
            if names:
                parts.append(
                    "relations: "
                    + ", ".join(sanitize_text(n, 30) for n in names[:MAX_RELATIONS])
                )
        except Exception:
            pass  # the entity line stands without its relations
        last = (entity.attrs or {}).get("last_contact")
        if entity.entity_type == "person" and last:
            parts.append(f"last contact {sanitize_text(last, 30)}")
        return ScreenLine(
            ref=ref,
            label=entity.canonical_name,
            summary="; ".join(parts),
            posture=ScreenPosture(source="memory"),
        )


class FactScreenResolver:
    kinds = frozenset({"fact"})

    def __init__(self, retriever: Any) -> None:
        self._retriever = retriever

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, self._load)

    async def _load(self, ref: ScreenRef) -> ScreenLine | None:
        fact_id = parse_uuid(ref.id)
        facts = await self._retriever.get_facts_by_ids([fact_id]) if fact_id else []
        if not facts:
            return None
        fact = facts[0]
        # The value as a sentence; the raw predicate key (snake_case) never reaches the user's model.
        sentence = sanitize_text(f"{_words(fact.predicate)}: {fact.value}", 160)
        review = "reviewed" if fact.reviewed else "not yet reviewed"
        if fact.contradicted:
            review = "contradicted"
        return ScreenLine(
            ref=ref,
            label=sanitize_text(fact.value, 80),
            summary=f"{sentence}; {review}",
            posture=ScreenPosture(
                kind=fact.claim_kind,
                source=_words(fact.provenance),
                confidence=fact.confidence,
                updated_at=as_utc(fact.created_at),
            ),
        )


class ProcedureScreenResolver:
    kinds = frozenset({"procedure"})

    def __init__(self, procedure_store: Any) -> None:
        self._procedures = procedure_store

    async def resolve(
        self, refs: list[ScreenRef], ctx: ResolveContext
    ) -> list[ScreenLine]:
        return await resolve_each(refs, self._load)

    async def _load(self, ref: ScreenRef) -> ScreenLine | None:
        procedure_id = parse_uuid(ref.id)
        identity = (
            await self._procedures.get_identity(procedure_id) if procedure_id else None
        )
        if identity is None:
            return None
        versions = await self._procedures.list_versions(procedure_id)
        active = next((v for v in versions if v.id == identity.active_version_id), None)
        parts = [_words(identity.status)]
        if active is not None:
            parts.append(f"version {active.version_number} ({_words(active.status)})")
            parts.append(f"{len(active.steps)} steps")
        return ScreenLine(
            ref=ref,
            label=identity.canonical_name,
            summary=", ".join(parts),
            posture=ScreenPosture(
                source="procedure", updated_at=as_utc(identity.updated_at)
            ),
        )


def build_screen_resolvers(
    *, retriever: Any, graph_store: Any, procedure_store: Any | None = None
) -> list[ScreenResolver]:
    resolvers: list[ScreenResolver] = [
        EntityScreenResolver(retriever, graph_store),
        FactScreenResolver(retriever),
    ]
    if procedure_store is not None:
        resolvers.append(ProcedureScreenResolver(procedure_store))
    return resolvers
